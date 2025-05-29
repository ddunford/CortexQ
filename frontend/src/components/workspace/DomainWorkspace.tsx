'use client';

import React, { useState, useEffect } from 'react';
import { 
  MessageCircle, 
  FileText, 
  Search, 
  Link, 
  BarChart3,
  Settings,
  Users,
  Globe,
  Shield,
  Activity,
  TrendingUp,
  Brain,
  Upload,
  Filter,
  Download,
  Eye,
  Edit,
  Trash2,
  Send,
  ArrowLeft,
  Bug,
  Code,
  X,
  Book,
  ExternalLink,
  Database,
  FileIcon,
  Clock,
  User,
  AlertCircle
} from 'lucide-react';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import CitationText from '../ui/CitationText';
import { Organization, Domain, Document, ConnectorConfig, AnalyticsMetrics, ApiResponse } from '../../types';
import { api } from '../../utils/api';
import { ConnectorConfigModal } from '../connectors/ConnectorConfigModal';
import WebScraperManager from '../connectors/WebScraperManager';
import ScraperManagement from '../knowledge/ScraperManagement';

interface DomainWorkspaceProps {
  domain: Domain;
  activeSection?: SectionType;
  onSectionChange?: (section: SectionType) => void;
  onEditDomain: () => void;
  onDeleteDomain: () => void;
}

type SectionType = 'chat' | 'sources' | 'analytics' | 'audit' | 'settings';

interface SearchResult {
  id: string;
  title: string;
  snippet: string;
  confidence: number;
  score: number;
  type: string;
  metadata?: any;
}

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: any[];
  confidence?: number;
}

interface AuditEvent {
  id: string;
  event_type: string;
  resource_type: string;
  action: string;
  description: string;
  created_at: string;
  username: string;
}

interface AuditAnalytics {
  total_events: number;
  unique_users: number;
  event_types: Array<{
    event_type: string;
    count: number;
    unique_users: number;
    percentage: number;
  }>;
  recent_events: AuditEvent[];
  time_range_days: number;
}

const DomainWorkspace: React.FC<DomainWorkspaceProps> = ({
  domain,
  activeSection = 'chat',
  onSectionChange,
  onEditDomain,
  onDeleteDomain,
}) => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [auditData, setAuditData] = useState<AuditAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  
  // Connector modal state
  const [showConnectorModal, setShowConnectorModal] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<ConnectorConfig | null>(null);
  
  // File upload state
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  // Reindexing state
  const [reindexing, setReindexing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<any>(null);

  // File view modal state
  const [viewModalOpen, setViewModalOpen] = useState(false);
  const [selectedFile, setSelectedFile] = useState<Document | null>(null);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const chatContainerRef = React.useRef<HTMLDivElement>(null);

  // Stabilize selectedConnector to prevent re-render issues
  const stableSelectedConnector = React.useMemo(() => {
    if (!selectedConnector) return null;
    
    // Ensure the connector has all required properties
    return {
      ...selectedConnector,
      type: selectedConnector.type || 'unknown',
      authConfig: selectedConnector.authConfig || {},
      syncConfig: selectedConnector.syncConfig || {},
      mappingConfig: selectedConnector.mappingConfig || {}
    };
  }, [selectedConnector?.id, selectedConnector?.type, selectedConnector?.name]);

  const sidebarSections = [
    { 
      id: 'chat', 
      label: 'AI Assistant', 
      icon: MessageCircle, 
      description: 'Chat with domain AI' 
    },
    { 
      id: 'sources', 
      label: 'Data Sources', 
      icon: Database, 
      description: 'Files and external integrations' 
    },
    { 
      id: 'analytics', 
      label: 'Analytics', 
      icon: BarChart3, 
      description: 'Usage insights and metrics' 
    },
    { 
      id: 'audit', 
      label: 'Audit', 
      icon: Shield, 
      description: 'Activity logs and compliance' 
    },
    { 
      id: 'settings', 
      label: 'Settings', 
      icon: Settings, 
      description: 'Domain configuration' 
    },
  ];

  useEffect(() => {
    loadWorkspaceData();
  }, [domain.id, activeSection]);

  // Auto-scroll chat to bottom when new messages are added
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const loadWorkspaceData = async () => {
    setLoading(true);
    try {
      switch (activeSection) {
        case 'sources':
          // Load both files and connectors for data sources section
          const [docsResponse, connectorsResponse] = await Promise.all([
            api.getFiles(domain.id),
            api.getConnectors(domain.id)
          ]);
          
          if (docsResponse.success) {
            const files = docsResponse.data?.files || [];
            const mappedFiles = files.map((file: any) => ({
              ...file,
              id: file.id,
              filename: file.filename,
              size: file.size_bytes,
              createdAt: file.upload_date,
              status: file.processed === true ? 'indexed' : 
                     file.processing_status === 'error' ? 'error' : 'processing'
            }));
            setDocuments(mappedFiles);
          }
          
          if (connectorsResponse.success && connectorsResponse.data) {
            // Handle both array response and object with connectors property
            const connectorList = Array.isArray(connectorsResponse.data) 
              ? connectorsResponse.data 
              : connectorsResponse.data.connectors || [];
              
            const mappedConnectors = connectorList.map((connector: any) => {
              return {
                id: connector.id,
                type: connector.type || connector.connector_type || 'unknown',
                name: connector.name,
                isEnabled: connector.isEnabled ?? connector.is_enabled ?? true,
                status: connector.status || 'pending',
                lastSync: connector.lastSync || connector.last_sync_at || null,
                authConfig: connector.authConfig || connector.auth_config || {},
                syncConfig: connector.syncConfig || connector.sync_config || {},
                mappingConfig: connector.mappingConfig || connector.mapping_config || {}
              };
            });
            setConnectors(mappedConnectors);
          } else {
            setConnectors([]);
          }
          
          // Load processing status for files
          loadProcessingStatus();
          break;
          
        case 'analytics':
          const analyticsResponse = await api.getAnalytics(domain.id);
          if (analyticsResponse.success) {
            setAnalytics(analyticsResponse.data);
          }
          break;
          
        case 'audit':
          const auditResponse = await api.getAuditAnalytics();
          if (auditResponse.success) {
            setAuditData(auditResponse.data);
          }
          break;
      }
    } catch (error) {
      console.error('Failed to load workspace data:', error);
    } finally {
      setLoading(false);
    }
  };

  const getDomainIcon = () => {
    const iconMap: Record<string, React.ReactNode> = {
      support: <Shield className="h-6 w-6" />,
      sales: <TrendingUp className="h-6 w-6" />,
      engineering: <Settings className="h-6 w-6" />,
      product: <Activity className="h-6 w-6" />,
      general: <Globe className="h-6 w-6" />,
    };
    const domainKey = (domain.domain_name || domain.display_name || domain.name || '').toLowerCase();
  return iconMap[domainKey] || <Globe className="h-6 w-6" />;
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'text-green-600 bg-green-100';
      case 'draft': return 'text-yellow-600 bg-yellow-100';
      case 'configuring': return 'text-blue-600 bg-blue-100';
      case 'inactive': return 'text-gray-600 bg-gray-100';
      case 'error': return 'text-red-600 bg-red-100';
      default: return 'text-gray-600 bg-gray-100';
    }
  };

  const handleFilterChange = (filterType: 'documents' | 'conversations' | 'externalData') => {
    setSearchFilters(prev => ({
      ...prev,
      [filterType]: !prev[filterType]
    }));
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    try {
      // Build content type filters based on selected filters
      const includeContentTypes: string[] = [];
      if (searchFilters.documents) {
        includeContentTypes.push('document/file', 'application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain', 'text/markdown', 'application/json', 'text/csv', 'application/x-yaml');
      }
      if (searchFilters.conversations) {
        includeContentTypes.push('chat/user', 'chat/assistant', 'conversation/session');
      }
      if (searchFilters.externalData) {
        includeContentTypes.push('api/jira', 'api/github', 'api/confluence', 'web/crawled');
      }

      const response = await api.search({
        query: searchQuery,
        domainId: domain.id, // Use domain ID
        filters: {
          documentTypes: includeContentTypes.length > 0 ? includeContentTypes : undefined
        },
        mode: 'hybrid',
        limit: 20,
        offset: 0,
      });
      
      if (response.success && response.data) {
        // Backend returns SearchResponse with results array
        const searchResponse = response.data;
        setSearchResults(searchResponse.results || []);
        console.log('Search completed:', {
          query: searchQuery,
          totalFound: searchResponse.total_found,
          resultsCount: searchResponse.results?.length || 0,
          searchTime: searchResponse.search_time_ms,
          filters: searchFilters
        });
      }
    } catch (error) {
      console.error('Search failed:', error);
      setSearchResults([]);
    } finally {
      setLoading(false);
    }
  };

  // File upload handlers
  const handleUploadClick = () => {
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []);
    if (files.length === 0) return;

    setUploading(true);
    try {
      for (const file of files) {
        const uploadResponse = await api.uploadFile(file, domain.id);
        if (!uploadResponse.success) {
          // Handle upload failure silently or with proper error reporting
        }
      }
      
      // Reload documents after upload
      await loadWorkspaceData();
    } catch (error) {
      console.error('File upload failed:', error);
    } finally {
      setUploading(false);
      // Reset file input
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  // Reindexing functions
  const loadProcessingStatus = async () => {
    try {
      const response = await api.getProcessingStatus(domain.id);
      if (response.success) {
        setProcessingStatus(response.data);
      }
    } catch (error) {
      console.error('Failed to load processing status:', error);
    }
  };

  const handleReindex = async (force: boolean = false) => {
    if (!confirm(force ? 
      'This will reindex ALL documents in this domain, including already processed ones. This may take several minutes. Continue?' :
      'This will reindex unprocessed and failed documents. Continue?'
    )) {
      return;
    }

    setReindexing(true);
    try {
      const response = await api.reindexFiles(domain.id, force);
      
      if (response.success) {
        alert(`Successfully queued ${response.data.files_queued} files for reindexing. Estimated completion: ${response.data.estimated_completion}`);
        // Reload data to show updated status
        await loadWorkspaceData();
        await loadProcessingStatus();
      } else {
        const errorMessage = typeof response.message === 'string' 
          ? response.message 
          : 'Unknown error occurred';
        alert(`Reindexing failed: ${errorMessage}`);
      }
    } catch (error) {
      console.error('Reindexing failed:', error);
      alert('Reindexing failed. Please try again.');
    } finally {
      setReindexing(false);
    }
  };

  // File action handlers
  const handleViewFile = async (file: Document) => {
    try {
      const response = await api.getFile(file.id);
      if (response.success) {
        setSelectedFile(response.data);
        setViewModalOpen(true);
      }
    } catch (error) {
      console.error('Failed to view file:', error);
      alert('Failed to view file details');
    }
  };

  const handleDownloadFile = async (file: Document) => {
    try {
      const response = await api.downloadFile(file.id);
      if (response.success && response.data) {
        // Open the download URL in a new tab/window
        const link = document.createElement('a');
        link.href = response.data.download_url;
        link.download = response.data.filename;
        link.target = '_blank';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
      } else {
        alert('Failed to generate download link');
      }
    } catch (error) {
      console.error('Failed to download file:', error);
      alert('Failed to download file. Please try again.');
    }
  };

  const handleDeleteFile = async (file: Document) => {
    if (!confirm(`Are you sure you want to delete "${file.filename}"? This action cannot be undone.`)) {
      return;
    }

    try {
      const response = await api.deleteFile(file.id);
      if (response.success) {
        // Remove the file from the local state
        setDocuments(docs => docs.filter(d => d.id !== file.id));
        alert('File deleted successfully');
      } else {
        alert('Failed to delete file');
      }
    } catch (error) {
      console.error('Failed to delete file:', error);
      alert('Failed to delete file');
    }
  };

  // Chat functions
  const handleSendMessage = async () => {
    if (!chatInput.trim() || chatLoading) return;

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: chatInput.trim(),
      timestamp: new Date(),
    };

    setChatMessages(prev => [...prev, userMessage]);
    setChatInput('');
    setChatLoading(true);

    try {
      const response = await api.sendMessage({
        message: userMessage.content,
        domainId: domain.id,
        sessionId: sessionId || undefined,
      });

      if (response.success) {
        const assistantMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: response.data.response || 'I received your message but couldn\'t generate a response.',
          timestamp: new Date(),
          sources: response.data.sources || [],
          confidence: response.data.confidence || 0,
        };

        setChatMessages(prev => [...prev, assistantMessage]);
        
        // Set session ID if not already set - note: session_id might not be on Message type
        // This would need to be handled differently based on actual API response structure
      } else {
        const errorMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: `Sorry, I encountered an error: ${typeof response.message === 'string' ? response.message : 'Unknown error occurred'}`,
          timestamp: new Date(),
        };
        setChatMessages(prev => [...prev, errorMessage]);
      }
    } catch (error) {
      console.error('Chat error:', error);
      const errorMessage: ChatMessage = {
        id: (Date.now() + 1).toString(),
        type: 'assistant',
        content: 'Sorry, I\'m having trouble connecting right now. Please try again.',
        timestamp: new Date(),
      };
      setChatMessages(prev => [...prev, errorMessage]);
    } finally {
      setChatLoading(false);
    }
  };

  const handleChatKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  const formatTimestamp = (timestamp: Date) => {
    return timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  const handleConnectorCreated = (connector: ConnectorConfig) => {
    // Apply the same mapping logic as loadWorkspaceData to ensure consistency
    console.log('New connector created:', connector);
    
    // Handle both string and enum cases for connector_type
    let connectorType = 'unknown';
    if (connector.connector_type) {
      if (typeof connector.connector_type === 'string') {
        connectorType = connector.connector_type;
      } else if (connector.connector_type.value) {
        connectorType = connector.connector_type.value;
      } else if (connector.connector_type.toString) {
        connectorType = connector.connector_type.toString();
      }
    }
    
    const mappedConnector = {
      id: connector.id,
      type: connectorType,
      name: connector.name,
      isEnabled: connector.is_enabled || true,
      status: connector.status || 'pending',
      lastSync: connector.last_sync_at || null,
      authConfig: connector.auth_config || {},
      syncConfig: connector.sync_config || {},
      mappingConfig: connector.mapping_config || {}
    };
    
    console.log('Mapped new connector:', mappedConnector);
    setConnectors(prev => [...prev, mappedConnector]);
    setShowConnectorModal(false);
  };

  const handleConnectorUpdated = (updatedConnector: ConnectorConfig) => {
    setConnectors(prev => prev.map(c => c.id === updatedConnector.id ? updatedConnector : c));
  };

  const handleConnectorSelect = (connector: ConnectorConfig) => {
    setSelectedConnector(connector);
  };

  const handleBackToConnectors = () => {
    setSelectedConnector(null);
  };

  const handleConnectorDelete = async (connectorId: string, connectorName: string) => {
    if (!confirm(`Are you sure you want to delete "${connectorName}"? This action cannot be undone and will remove all associated data.`)) {
      return;
    }

    try {
      const response = await api.deleteConnector(domain.id, connectorId);
      
      if (response.success) {
        // Remove connector from state
        setConnectors(prev => prev.filter(c => c.id !== connectorId));
        
        // If this connector is currently selected, go back to list
        if (selectedConnector?.id === connectorId) {
          setSelectedConnector(null);
        }
        
        alert('Data source deleted successfully');
      } else {
        alert(`Failed to delete data source: ${response.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to delete connector:', error);
      alert('Failed to delete data source. Please try again.');
    }
  };

  const renderDataSources = () => {
    if (selectedConnector) {
      if (selectedConnector.type === 'web_scraper') {
        return (
          <div>
            <div className="flex items-center space-x-4 mb-6">
              <Button
                variant="outline"
                icon={<ArrowLeft className="h-4 w-4" />}
                onClick={handleBackToConnectors}
              >
                Back to Data Sources
              </Button>
              <h2 className="text-xl font-semibold text-gray-900">{selectedConnector.name}</h2>
            </div>
            <WebScraperManager 
              connector={stableSelectedConnector}
              domainId={domain.id}
              onConnectorUpdated={handleConnectorUpdated}
            />
          </div>
        );
      } else {
        return (
          <div>
            <div className="flex items-center space-x-4 mb-6">
              <Button
                variant="outline"
                icon={<ArrowLeft className="h-4 w-4" />}
                onClick={handleBackToConnectors}
              >
                Back to Data Sources
              </Button>
              <h2 className="text-xl font-semibold text-gray-900">{selectedConnector.name}</h2>
            </div>
            <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
              <p className="text-yellow-800">
                Management interface for {selectedConnector.type} connectors coming soon.
              </p>
            </div>
          </div>
        );
      }
    }

    return (
      <div className="space-y-6">
        {/* Files Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <FileText className="h-5 w-5" />
                <span>File Library</span>
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">Upload and manage documents for this domain</p>
            </div>
            <div className="flex items-center space-x-2">
              <Button 
                variant="outline" 
                icon={<Upload className="h-4 w-4" />}
                onClick={handleUploadClick}
                disabled={uploading}
              >
                {uploading ? 'Uploading...' : 'Upload Files'}
              </Button>
              {documents.length > 0 && (
                <Button 
                  variant="outline" 
                  icon={<Brain className="h-4 w-4" />}
                  onClick={() => handleReindex()}
                  disabled={reindexing}
                >
                  {reindexing ? 'Reindexing...' : 'Reindex All'}
                </Button>
              )}
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <div className="text-center">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="text-gray-500 mt-2">Loading files...</p>
                </div>
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8">
                <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No files uploaded</h3>
                <p className="text-gray-500 mb-4">Upload documents to start building your knowledge base</p>
                <Button icon={<Upload className="h-4 w-4" />} onClick={handleUploadClick}>
                  Upload Your First File
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {documents.map((doc) => (
                  <div key={doc.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <FileText className="h-5 w-5 text-gray-400" />
                      <div>
                        <p className="font-medium text-gray-900">{doc.filename}</p>
                        <p className="text-sm text-gray-500">
                          {((doc.size || 0) / 1024).toFixed(1)} KB • {new Date(doc.createdAt).toLocaleDateString()}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(doc.status)}`}>
                        {doc.status}
                      </span>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        icon={<Eye className="h-4 w-4" />}
                        onClick={() => handleViewFile(doc)}
                      >
                        View
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        icon={<Download className="h-4 w-4" />}
                        onClick={() => handleDownloadFile(doc)}
                      >
                        Download
                      </Button>
                      <Button 
                        variant="danger" 
                        size="sm" 
                        icon={<Trash2 className="h-4 w-4" />}
                        onClick={() => handleDeleteFile(doc)}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
                
                {processingStatus && processingStatus.queue_length > 0 && (
                  <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
                    <div className="flex items-center space-x-2">
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                      <span className="text-blue-800 font-medium">Processing files...</span>
                    </div>
                    <p className="text-blue-700 text-sm mt-1">
                      {processingStatus.queue_length} files in processing queue
                    </p>
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* External Connectors Section */}
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle className="flex items-center space-x-2">
                <Link className="h-5 w-5" />
                <span>External Data Sources</span>
              </CardTitle>
              <p className="text-sm text-gray-600 mt-1">Connect external platforms and services</p>
            </div>
            <Button
              icon={<Link className="h-4 w-4" />}
              onClick={() => setShowConnectorModal(true)}
            >
              Add Connector
            </Button>
          </CardHeader>
          <CardContent>
            {connectors.length === 0 ? (
              <div className="text-center py-8">
                <Link className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No external sources connected</h3>
                <p className="text-gray-500 mb-4">Connect external data sources like Jira, GitHub, or web scrapers</p>
                <Button icon={<Link className="h-4 w-4" />} onClick={() => setShowConnectorModal(true)}>
                  Add Your First Connector
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                {connectors.map((connector) => (
                  <div key={connector.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className={`p-2 rounded-lg ${connector.isEnabled ? 'bg-green-100' : 'bg-gray-100'}`}>
                        <Link className={`h-5 w-5 ${connector.isEnabled ? 'text-green-600' : 'text-gray-400'}`} />
                      </div>
                      <div>
                        <h4 className="font-medium text-gray-900">{connector.name}</h4>
                        <p className="text-sm text-gray-500 capitalize">{connector.type.replace('_', ' ')}</p>
                        {connector.lastSync && (
                          <p className="text-xs text-gray-400">Last sync: {new Date(connector.lastSync).toLocaleString()}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connector.status)}`}>
                        {connector.status}
                      </span>
                      <Button 
                        variant="outline" 
                        size="sm"
                        onClick={() => handleConnectorSelect(connector)}
                      >
                        {connector.type === 'web_scraper' ? 'Manage' : 'Configure'}
                      </Button>
                      <Button 
                        variant="outline" 
                        size="sm" 
                        icon={<Edit className="h-4 w-4" />}
                        onClick={() => {
                          setSelectedConnector(connector);
                          setShowConnectorModal(true);
                        }}
                      >
                        Edit
                      </Button>
                      <Button 
                        variant="danger" 
                        size="sm" 
                        icon={<Trash2 className="h-4 w-4" />}
                        onClick={() => handleConnectorDelete(connector.id, connector.name)}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    );
  };

  const renderAudit = () => (
    <div className="space-y-6">
      {loading ? (
        <div className="flex items-center justify-center py-12">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            <p className="text-gray-500 mt-2">Loading audit data...</p>
          </div>
        </div>
      ) : !auditData ? (
        <div className="text-center py-12">
          <AlertCircle className="h-12 w-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No audit data available</h3>
          <p className="text-gray-500">Audit logging may not be enabled for this domain</p>
        </div>
      ) : (
        <>
          {/* Audit Overview */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <Activity className="h-8 w-8 text-blue-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Total Events</p>
                    <p className="text-2xl font-bold text-gray-900">{auditData.total_events.toLocaleString()}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <Users className="h-8 w-8 text-green-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Active Users</p>
                    <p className="text-2xl font-bold text-gray-900">{auditData.unique_users}</p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardContent className="p-6">
                <div className="flex items-center">
                  <Clock className="h-8 w-8 text-purple-600" />
                  <div className="ml-4">
                    <p className="text-sm font-medium text-gray-600">Time Range</p>
                    <p className="text-2xl font-bold text-gray-900">{auditData.time_range_days} days</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Event Types Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Event Types Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {auditData.event_types.map((eventType, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <div className="flex items-center space-x-3">
                      <div className="w-3 h-3 rounded-full bg-blue-500"></div>
                      <span className="font-medium text-gray-900">{eventType.event_type}</span>
                    </div>
                    <div className="flex items-center space-x-4">
                      <span className="text-sm text-gray-500">{eventType.unique_users} users</span>
                      <span className="font-semibold text-gray-900">{eventType.count}</span>
                      <span className="text-sm text-gray-500">({eventType.percentage}%)</span>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Recent Activity */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {auditData.recent_events.map((event, index) => (
                  <div key={index} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div className="flex items-center space-x-3">
                      <div className="flex-shrink-0">
                        <User className="h-5 w-5 text-gray-400" />
                      </div>
                      <div>
                        <p className="font-medium text-gray-900">{event.description}</p>
                        <p className="text-sm text-gray-500">
                          {event.username} • {event.event_type} • {event.resource_type}
                        </p>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-500">
                        {new Date(event.created_at).toLocaleDateString()}
                      </p>
                      <p className="text-xs text-gray-400">
                        {new Date(event.created_at).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );

  const renderChat = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">AI Assistant</h3>
          <p className="text-gray-600">Chat with the domain-specific AI assistant about your uploaded documents</p>
        </div>
        {sessionId && (
          <div className="text-sm text-gray-500">
            Session: {sessionId.slice(0, 8)}...
          </div>
        )}
      </div>

      <Card className="h-96">
        <CardContent className="h-full flex flex-col">
          <div 
            ref={chatContainerRef}
            className="flex-1 p-4 bg-gray-50 rounded-lg mb-4 overflow-y-auto space-y-3"
          >
            {chatMessages.length === 0 ? (
              <div className="text-center text-gray-500 h-full flex flex-col items-center justify-center">
                <Brain className="h-12 w-12 mx-auto mb-2" />
                <p className="mb-2">Start a conversation with the AI assistant</p>
                <p className="text-sm">Ask questions about your uploaded documents, search for information, or get help with domain-specific topics.</p>
              </div>
            ) : (
              chatMessages.map((message) => (
                <div
                  key={message.id}
                  className={`flex ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  <div
                    className={`max-w-xs lg:max-w-md px-3 py-2 rounded-lg ${
                      message.type === 'user'
                        ? 'bg-blue-600 text-white'
                        : 'bg-white border border-gray-200 text-gray-900 shadow-sm'
                    }`}
                  >
                    {message.type === 'assistant' ? (
                      <div className="space-y-3">
                        <CitationText 
                          content={message.content} 
                          sources={message.sources}
                          className="text-sm leading-relaxed"
                        />
                        
                        {/* Confidence indicator */}
                        <div className="flex items-center justify-between text-xs">
                          <span className="text-gray-500">
                            {formatTimestamp(message.timestamp)}
                          </span>
                          {message.confidence && (
                            <div className="flex items-center space-x-1">
                              <div className={`w-2 h-2 rounded-full ${
                                message.confidence > 0.7 ? 'bg-green-500' : 
                                message.confidence > 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                              }`} />
                              <span className="text-gray-600 font-medium">
                                {Math.round(message.confidence * 100)}% confident
                              </span>
                            </div>
                          )}
                        </div>
                        
                        {/* Sources section */}
                        {message.sources && message.sources.length > 0 && (
                          <div className="pt-2 border-t border-gray-100">
                            <div className="flex items-center space-x-1 mb-2">
                              <Book className="h-3 w-3 text-gray-500" />
                              <span className="text-xs text-gray-500 font-medium">
                                Sources ({message.sources.length})
                              </span>
                            </div>
                            <div className="space-y-1">
                              {message.sources.slice(0, 3).map((source, idx) => {
                                const isWebPage = source.url;
                                const IconComponent = isWebPage ? ExternalLink : FileText;
                                
                                return (
                                  <div 
                                    key={idx} 
                                    className="flex items-center space-x-2 text-xs text-gray-600 hover:text-gray-800 transition-colors"
                                  >
                                    <IconComponent className="h-3 w-3 flex-shrink-0" />
                                    {isWebPage ? (
                                      <a 
                                        href={source.url} 
                                        target="_blank" 
                                        rel="noopener noreferrer"
                                        className="hover:underline truncate flex-1"
                                        title={source.title}
                                      >
                                        {source.title}
                                      </a>
                                    ) : (
                                      <span className="truncate flex-1" title={source.title}>
                                        {source.title}
                                      </span>
                                    )}
                                    <span className="text-gray-400 text-xs">
                                      {source.confidence_score}
                                    </span>
                                  </div>
                                );
                              })}
                              {message.sources.length > 3 && (
                                <div className="text-xs text-gray-500 italic">
                                  +{message.sources.length - 3} more sources
                                </div>
                              )}
                            </div>
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-sm">{message.content}</p>
                    )}
                    {message.type === 'user' && (
                      <div className="mt-1">
                        <span className="text-xs text-blue-100">
                          {formatTimestamp(message.timestamp)}
                        </span>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {chatLoading && (
              <div className="flex justify-start">
                <div className="bg-white border border-gray-200 text-gray-900 max-w-xs lg:max-w-md px-3 py-2 rounded-lg">
                  <div className="flex items-center space-x-2">
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                    <span className="text-sm">AI is thinking...</span>
                  </div>
                </div>
              </div>
            )}
          </div>
          <div className="flex space-x-2">
            <Input
              placeholder="Ask a question about this domain..."
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={handleChatKeyPress}
              disabled={chatLoading}
              fullWidth
            />
            <Button 
              onClick={handleSendMessage}
              disabled={chatLoading || !chatInput.trim()}
              icon={<Send className="h-4 w-4" />}
            >
              Send
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );

  const renderAnalytics = () => (
    <div className="space-y-6">
      {analytics && (
        <>
          {/* Key Metrics */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card padding="sm">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{analytics.totalQueries}</p>
                <p className="text-sm text-gray-600">Total Queries</p>
              </div>
            </Card>
            <Card padding="sm">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{analytics.activeUsers}</p>
                <p className="text-sm text-gray-600">Active Users</p>
              </div>
            </Card>
            <Card padding="sm">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{analytics.averageResponseTime}s</p>
                <p className="text-sm text-gray-600">Avg Response Time</p>
              </div>
            </Card>
            <Card padding="sm">
              <div className="text-center">
                <p className="text-2xl font-bold text-gray-900">{(analytics.successRate * 100).toFixed(1)}%</p>
                <p className="text-sm text-gray-600">Success Rate</p>
              </div>
            </Card>
          </div>

          {/* Top Queries */}
          <Card>
            <CardHeader>
              <CardTitle>Top Queries</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analytics.topQueries?.slice(0, 5).map((query, index) => (
                  <div key={index} className="flex items-center justify-between">
                    <div>
                      <p className="font-medium text-gray-900">{query.query}</p>
                      <p className="text-sm text-gray-500">{query.count} queries</p>
                    </div>
                    <div className="text-right">
                      <p className="text-sm text-gray-900">{(query.averageConfidence * 100).toFixed(1)}%</p>
                      <p className="text-xs text-gray-500">confidence</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );

  const renderSettings = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>Basic Information</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Name</label>
                <p className="text-gray-900">{domain.display_name || domain.name}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Description</label>
                <p className="text-gray-900">{domain.description}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Status</label>
                <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(domain.status)}`}>
                  {domain.status}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Access Control */}
        <Card>
          <CardHeader>
            <CardTitle>Access Control</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700">Visibility</label>
                <p className="text-gray-900">{domain.isPublic ? 'Public' : 'Private'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Access Level</label>
                <p className="text-gray-900 capitalize">{domain.settings?.securityConfig?.accessControl || 'Not configured'}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Audit Logging</label>
                <p className="text-gray-900">{domain.settings?.securityConfig?.enableAuditLogging ? 'Enabled' : 'Disabled'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  const renderSectionContent = () => {
    switch (activeSection) {
      case 'chat': return renderChat();
      case 'sources': return renderDataSources();
      case 'analytics': return renderAnalytics();
      case 'audit': return renderAudit();
      case 'settings': return renderSettings();
      default: return null;
    }
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.json,.csv,.yaml,.yml"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Main Content Area - Full Width */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Content Header */}
        <div className="bg-white border-b border-gray-200 px-8 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {sidebarSections.find(s => s.id === activeSection)?.label}
              </h2>
              <p className="text-gray-600 mt-1">
                {sidebarSections.find(s => s.id === activeSection)?.description}
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <Button 
                variant="outline" 
                icon={<Edit className="h-4 w-4" />} 
                onClick={onEditDomain}
              >
                Edit Domain
              </Button>
              <Button 
                variant="danger" 
                icon={<Trash2 className="h-4 w-4" />} 
                onClick={onDeleteDomain}
              >
                Delete Domain
              </Button>
            </div>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-auto p-8">
          {renderSectionContent()}
        </div>
      </div>

      {/* Modals remain the same */}
      {showConnectorModal && (
        <ConnectorConfigModal
          isOpen={showConnectorModal}
          onClose={() => {
            setShowConnectorModal(false);
            setSelectedConnector(null);
          }}
          domainId={domain.id}
          onConnectorCreated={handleConnectorCreated}
          onConnectorUpdated={handleConnectorUpdated}
        />
      )}

      {viewModalOpen && selectedFile && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[80vh] overflow-hidden">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">File Details</h3>
              <button
                onClick={() => {
                  setViewModalOpen(false);
                  setSelectedFile(null);
                }}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="h-6 w-6" />
              </button>
            </div>
            <div className="p-6 overflow-y-auto max-h-[calc(80vh-120px)]">
              <div className="space-y-4">
                <div className="flex items-center space-x-3">
                  <FileText className="h-12 w-12 text-gray-400" />
                  <div>
                    <h4 className="text-xl font-medium text-gray-900">{selectedFile.filename}</h4>
                    <p className="text-gray-500">{selectedFile.contentType}</p>
                  </div>
                </div>
                
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700">File Size</label>
                    <p className="text-sm text-gray-900">{((selectedFile.size || 0) / 1024).toFixed(1)} KB</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Status</label>
                    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(selectedFile.status)}`}>
                      {selectedFile.status}
                    </span>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Upload Date</label>
                    <p className="text-sm text-gray-900">{new Date(selectedFile.createdAt).toLocaleString()}</p>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700">Uploaded By</label>
                    <p className="text-sm text-gray-900">{selectedFile.uploadedBy || 'Unknown'}</p>
                  </div>
                </div>

                {selectedFile.metadata && Object.keys(selectedFile.metadata).length > 0 && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">Metadata</label>
                    <pre className="text-xs bg-gray-50 p-3 rounded-lg overflow-x-auto">
                      {JSON.stringify(selectedFile.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
            <div className="flex items-center justify-end space-x-3 p-4 border-t border-gray-200 bg-gray-50">
              <Button 
                variant="outline" 
                icon={<Download className="h-4 w-4" />}
                onClick={() => handleDownloadFile(selectedFile)}
              >
                Download
              </Button>
              <Button 
                variant="danger" 
                icon={<Trash2 className="h-4 w-4" />}
                onClick={() => {
                  setViewModalOpen(false);
                  setSelectedFile(null);
                  handleDeleteFile(selectedFile);
                }}
              >
                Delete
              </Button>
              <Button 
                variant="outline"
                onClick={() => {
                  setViewModalOpen(false);
                  setSelectedFile(null);
                }}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DomainWorkspace; 