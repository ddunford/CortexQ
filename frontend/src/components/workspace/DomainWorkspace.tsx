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
  Send
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import CitationText from '../ui/CitationText';
import { Domain, Document, SearchResult, AnalyticsMetrics, ConnectorConfig } from '../../types';
import { apiClient } from '../../utils/api';

interface DomainWorkspaceProps {
  domain: Domain;
  onEditDomain: () => void;
  onDeleteDomain: () => void;
}

type TabType = 'knowledge' | 'chat' | 'search' | 'sources' | 'analytics' | 'settings';

interface ChatMessage {
  id: string;
  type: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  sources?: any[];
  confidence?: number;
}

const DomainWorkspace: React.FC<DomainWorkspaceProps> = ({
  domain,
  onEditDomain,
  onDeleteDomain,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('knowledge');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchFilters, setSearchFilters] = useState({
    documents: true,
    conversations: true,
    externalData: true
  });
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  
  // File upload state
  const [uploading, setUploading] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);
  
  // Reindexing state
  const [reindexing, setReindexing] = useState(false);
  const [processingStatus, setProcessingStatus] = useState<any>(null);

  // Chat state
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const chatContainerRef = React.useRef<HTMLDivElement>(null);

  const tabs = [
    { id: 'knowledge', label: 'Knowledge Base', icon: FileText, description: 'Manage documents and files' },
    { id: 'chat', label: 'AI Assistant', icon: MessageCircle, description: 'Chat with domain AI' },
    { id: 'search', label: 'Search & Discovery', icon: Search, description: 'Advanced search capabilities' },
    { id: 'sources', label: 'Data Sources', icon: Link, description: 'External integrations' },
    { id: 'analytics', label: 'Analytics', icon: BarChart3, description: 'Usage insights' },
    { id: 'settings', label: 'Settings', icon: Settings, description: 'Domain configuration' },
  ];

  useEffect(() => {
    loadWorkspaceData();
    if (activeTab === 'knowledge') {
      loadProcessingStatus();
    }
  }, [domain.id, activeTab]);

  // Auto-scroll chat to bottom when new messages are added
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTop = chatContainerRef.current.scrollHeight;
    }
  }, [chatMessages]);

  const loadWorkspaceData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'knowledge':
          const docsResponse = await apiClient.getFiles(domain.domain_name);
          if (docsResponse.success) {
            // Map API response to frontend format
            const mappedFiles = (docsResponse.data.files || []).map((file: any) => ({
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
          break;
        case 'sources':
          const connectorsResponse = await apiClient.getConnectors(domain.id);
          if (connectorsResponse.success) {
            setConnectors(connectorsResponse.data);
          }
          break;
        case 'analytics':
          const analyticsResponse = await apiClient.getAnalytics(domain.id);
          if (analyticsResponse.success) {
            setAnalytics(analyticsResponse.data);
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

      const response = await apiClient.search({
        query: searchQuery,
        domainId: domain.domain_name, // Use domain name instead of ID
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
        const uploadResponse = await apiClient.uploadFile(file, domain.domain_name);
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
      const response = await apiClient.request('/files/processing-status', {
        method: 'GET',
        params: { domain: domain.domain_name }
      });
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
      const response = await apiClient.request('/files/reindex', {
        method: 'POST',
        body: JSON.stringify({ 
          domain: domain.domain_name, 
          force: force 
        })
      });
      
      if (response.success) {
        alert(`Successfully queued ${response.data.files_queued} files for reindexing. Estimated completion: ${response.data.estimated_completion}`);
        // Reload data to show updated status
        await loadWorkspaceData();
        await loadProcessingStatus();
      } else {
        alert(`Reindexing failed: ${response.message}`);
      }
    } catch (error) {
      console.error('Reindexing failed:', error);
      alert('Reindexing failed. Please try again.');
    } finally {
      setReindexing(false);
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
      const response = await apiClient.sendMessage({
        message: userMessage.content,
        domain: domain.domain_name,
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
        
        // Set session ID if not already set
        if (!sessionId && response.data.session_id) {
          setSessionId(response.data.session_id);
        }
      } else {
        const errorMessage: ChatMessage = {
          id: (Date.now() + 1).toString(),
          type: 'assistant',
          content: `Sorry, I encountered an error: ${response.message}`,
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

  const renderKnowledgeBase = () => (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Knowledge Base</h3>
          <p className="text-gray-600">Manage documents and files for this domain</p>
        </div>
        <div className="flex space-x-3">
          <Button variant="outline" icon={<Filter className="h-4 w-4" />}>
            Filter
          </Button>
          <Button 
            variant="outline"
            icon={<Brain className="h-4 w-4" />}
            onClick={() => handleReindex(false)}
            loading={reindexing}
          >
            Reindex Failed
          </Button>
          <Button 
            variant="outline"
            icon={<Activity className="h-4 w-4" />}
            onClick={() => handleReindex(true)}
            loading={reindexing}
          >
            Force Reindex All
          </Button>
          <Button 
            icon={<Upload className="h-4 w-4" />}
            onClick={handleUploadClick}
            loading={uploading}
          >
            Upload Files
          </Button>
        </div>
      </div>

      {/* Processing Status */}
      {processingStatus && (
        <Card>
          <CardHeader>
            <CardTitle>Processing Status</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="space-y-2">
                <h4 className="font-medium text-gray-900">Files</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Total:</span>
                    <span className="font-medium">{processingStatus.files?.total || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Processed:</span>
                    <span className="font-medium text-green-600">{processingStatus.files?.processed || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Pending:</span>
                    <span className="font-medium text-yellow-600">{processingStatus.files?.pending || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Failed:</span>
                    <span className="font-medium text-red-600">{processingStatus.files?.failed || 0}</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="font-medium text-gray-900">Embeddings</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Total Embeddings:</span>
                    <span className="font-medium">{processingStatus.embeddings?.total_embeddings || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Files with Embeddings:</span>
                    <span className="font-medium">{processingStatus.embeddings?.files_with_embeddings || 0}</span>
                  </div>
                </div>
              </div>
              <div className="space-y-2">
                <h4 className="font-medium text-gray-900">Active Jobs</h4>
                <div className="space-y-1 text-sm">
                  <div className="flex justify-between">
                    <span>Pending Jobs:</span>
                    <span className="font-medium text-blue-600">{processingStatus.processing_jobs?.pending || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span>Running Jobs:</span>
                    <span className="font-medium text-orange-600">{processingStatus.processing_jobs?.running || 0}</span>
                  </div>
                </div>
              </div>
            </div>
            {(processingStatus.processing_jobs?.active || 0) > 0 && (
              <div className="mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                <div className="flex items-center space-x-2">
                  <Activity className="h-4 w-4 text-blue-600 animate-spin" />
                  <span className="text-sm text-blue-800">
                    Processing {processingStatus.processing_jobs.active} files in the background...
                  </span>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card padding="sm">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">{documents.length}</p>
            <p className="text-sm text-gray-600">Total Documents</p>
          </div>
        </Card>
        <Card padding="sm">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">
              {documents.filter(d => d.status === 'indexed').length}
            </p>
            <p className="text-sm text-gray-600">Indexed</p>
          </div>
        </Card>
        <Card padding="sm">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">
              {documents.filter(d => d.status === 'processing').length}
            </p>
            <p className="text-sm text-gray-600">Processing</p>
          </div>
        </Card>
        <Card padding="sm">
          <div className="text-center">
            <p className="text-2xl font-bold text-gray-900">
              {Math.round(documents.reduce((acc, d) => acc + (d.size || d.size_bytes || 0), 0) / 1024 / 1024)}MB
            </p>
            <p className="text-sm text-gray-600">Total Size</p>
          </div>
        </Card>
      </div>

      {/* Documents List */}
      <Card>
        <CardHeader>
          <CardTitle>Documents</CardTitle>
        </CardHeader>
        <CardContent>
          {documents.length === 0 ? (
            <div className="text-center py-8">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No documents yet</h3>
              <p className="text-gray-500 mb-4">Upload your first document to get started.</p>
              <Button 
                icon={<Upload className="h-4 w-4" />}
                onClick={handleUploadClick}
                loading={uploading}
              >
                Upload Document
              </Button>
            </div>
          ) : (
            <div className="space-y-3">
              {documents.map((doc) => (
                <div key={doc.id} className="flex items-center justify-between p-4 border border-gray-200 rounded-lg">
                  <div className="flex items-center space-x-3">
                    <FileText className="h-8 w-8 text-gray-400" />
                    <div>
                      <h4 className="font-medium text-gray-900">{doc.filename}</h4>
                      <p className="text-sm text-gray-500">
                        {((doc.size || doc.size_bytes || 0) / 1024).toFixed(1)}KB • {new Date(doc.createdAt || doc.upload_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(doc.status)}`}>
                      {doc.status}
                    </span>
                    <Button variant="ghost" size="sm" icon={<Eye className="h-4 w-4" />}>View</Button>
                    <Button variant="ghost" size="sm" icon={<Download className="h-4 w-4" />}>Download</Button>
                    <Button variant="ghost" size="sm" icon={<Trash2 className="h-4 w-4" />}>Delete</Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
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
                        : 'bg-white border border-gray-200 text-gray-900'
                    }`}
                  >
                    {message.type === 'assistant' ? (
                      <CitationText 
                        content={message.content} 
                        sources={message.sources}
                        className="text-sm"
                      />
                    ) : (
                      <p className="text-sm">{message.content}</p>
                    )}
                    <div className="flex items-center justify-between mt-1">
                      <span className={`text-xs ${
                        message.type === 'user' ? 'text-blue-100' : 'text-gray-500'
                      }`}>
                        {formatTimestamp(message.timestamp)}
                      </span>
                      {message.type === 'assistant' && message.confidence && (
                        <span className="text-xs text-gray-500">
                          {Math.round(message.confidence * 100)}% confident
                        </span>
                      )}
                    </div>
                    {message.sources && message.sources.length > 0 && (
                      <div className="mt-2 pt-2 border-t border-gray-200">
                        <p className="text-xs text-gray-500 mb-1">Sources:</p>
                        {message.sources.slice(0, 2).map((source, idx) => (
                          <div key={idx} className="text-xs text-gray-600">
                            • {source.title || 'Document'}
                          </div>
                        ))}
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

  const renderSearch = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Search & Discovery</h3>
          <p className="text-gray-600">Advanced search across all domain content</p>
        </div>
      </div>

      {/* Search Interface */}
      <Card>
        <CardContent>
          <div className="flex space-x-2 mb-4">
            <Input
              placeholder="Search documents, conversations, and data..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
              fullWidth
            />
            <Button onClick={handleSearch} loading={loading} icon={<Search className="h-4 w-4" />}>
              Search
            </Button>
          </div>
          
          <div className="flex items-center justify-between">
            <div className="flex space-x-4 text-sm">
              <label className="flex items-center space-x-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  className="rounded" 
                  checked={searchFilters.documents}
                  onChange={() => handleFilterChange('documents')}
                />
                <span>Documents</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  className="rounded" 
                  checked={searchFilters.conversations}
                  onChange={() => handleFilterChange('conversations')}
                />
                <span>Conversations</span>
              </label>
              <label className="flex items-center space-x-2 cursor-pointer">
                <input 
                  type="checkbox" 
                  className="rounded" 
                  checked={searchFilters.externalData}
                  onChange={() => handleFilterChange('externalData')}
                />
                <span>External Data</span>
              </label>
            </div>
            <div className="flex space-x-2">
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => setSearchFilters({ documents: true, conversations: true, externalData: true })}
              >
                Select All
              </Button>
              <Button 
                variant="ghost" 
                size="sm"
                onClick={() => setSearchFilters({ documents: false, conversations: false, externalData: false })}
              >
                Clear All
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Search Results ({searchResults.length})</CardTitle>
              <div className="flex items-center space-x-2 text-xs text-gray-500">
                <span>Filters:</span>
                {searchFilters.documents && <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">Documents</span>}
                {searchFilters.conversations && <span className="bg-green-100 text-green-800 px-2 py-1 rounded">Conversations</span>}
                {searchFilters.externalData && <span className="bg-purple-100 text-purple-800 px-2 py-1 rounded">External Data</span>}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {searchResults.map((result, index) => (
                <div key={`${result.id}-${index}`} className="border-b border-gray-200 pb-4 last:border-b-0">
                  <div className="flex items-start justify-between mb-2">
                    <h4 className="font-medium text-gray-900 flex-1">{result.title}</h4>
                    <div className="flex items-center space-x-2 text-xs text-gray-500 ml-4">
                      <span className="bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        {result.content_type}
                      </span>
                      <span className="bg-green-100 text-green-800 px-2 py-1 rounded">
                        {(result.confidence * 100).toFixed(1)}%
                      </span>
                    </div>
                  </div>
                  <p className="text-sm text-gray-600 mb-2 leading-relaxed">{result.snippet}</p>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <div className="flex items-center space-x-4">
                      <span>Domain: {result.domain}</span>
                      <span>Type: {result.source_type}</span>
                      {result.metadata?.chunk_index !== undefined && (
                        <span>Chunk: {result.metadata.chunk_index + 1}</span>
                      )}
                    </div>
                    <span>Score: {result.score.toFixed(3)}</span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* No Results Message */}
      {searchQuery && searchResults.length === 0 && !loading && (
        <Card>
          <CardContent>
            <div className="text-center py-8">
              <Search className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No results found</h3>
              <p className="text-gray-600">
                Try adjusting your search terms or check if documents are properly indexed in this domain.
              </p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  const renderDataSources = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Data Sources</h3>
          <p className="text-gray-600">External integrations and connectors</p>
        </div>
        <Button icon={<Link className="h-4 w-4" />}>
          Add Integration
        </Button>
      </div>

      {connectors.length === 0 ? (
        <Card>
          <CardContent className="text-center py-8">
            <Link className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No integrations yet</h3>
            <p className="text-gray-500 mb-4">Connect external data sources to enrich your domain.</p>
            <Button icon={<Link className="h-4 w-4" />}>Add Your First Integration</Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {connectors.map((connector) => (
            <Card key={connector.id} hover>
              <CardContent>
                <div className="flex items-center justify-between mb-3">
                  <div className="flex items-center space-x-3">
                    <div className="p-2 bg-gray-100 rounded-lg">
                      <Link className="h-5 w-5" />
                    </div>
                    <div>
                      <h4 className="font-medium text-gray-900">{connector.name}</h4>
                      <p className="text-sm text-gray-600 capitalize">{connector.type}</p>
                    </div>
                  </div>
                  <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(connector.status)}`}>
                    {connector.status}
                  </span>
                </div>
                <div className="flex items-center justify-between text-sm text-gray-500">
                  <span>Last sync: {connector.lastSync ? new Date(connector.lastSync).toLocaleDateString() : 'Never'}</span>
                  <Button variant="ghost" size="sm">Configure</Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );

  const renderAnalytics = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Analytics</h3>
          <p className="text-gray-600">Usage insights and performance metrics</p>
        </div>
      </div>

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
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">Domain Settings</h3>
          <p className="text-gray-600">Configure domain behavior and access</p>
        </div>
        <div className="flex space-x-3">
          <Button variant="outline" onClick={onEditDomain} icon={<Edit className="h-4 w-4" />}>
            Edit Domain
          </Button>
          <Button variant="danger" onClick={onDeleteDomain} icon={<Trash2 className="h-4 w-4" />}>
            Delete Domain
          </Button>
        </div>
      </div>

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
                <p className="text-gray-900 capitalize">{domain.settings.securityConfig.accessControl}</p>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700">Audit Logging</label>
                <p className="text-gray-900">{domain.settings.securityConfig.enableAuditLogging ? 'Enabled' : 'Disabled'}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );

  const renderTabContent = () => {
    switch (activeTab) {
      case 'knowledge': return renderKnowledgeBase();
      case 'chat': return renderChat();
      case 'search': return renderSearch();
      case 'sources': return renderDataSources();
      case 'analytics': return renderAnalytics();
      case 'settings': return renderSettings();
      default: return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        accept=".pdf,.docx,.txt,.md,.json,.csv,.yaml,.yml"
        onChange={handleFileSelect}
        className="hidden"
      />

      {/* Domain Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <div className={`p-3 rounded-xl ${domain.color || 'bg-blue-100'}`}>
            {getDomainIcon()}
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{domain.display_name || domain.name}</h1>
            <p className="text-gray-600">{domain.description}</p>
          </div>
        </div>
        <div className="flex items-center space-x-3">
          <span className={`px-3 py-1 text-sm font-medium rounded-full ${getStatusColor(domain.status)}`}>
            {domain.status}
          </span>
          <Button variant="outline" icon={<Users className="h-4 w-4" />}>
            Manage Access
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as TabType)}
              className={`flex items-center space-x-2 py-2 px-1 border-b-2 font-medium text-sm ${
                activeTab === tab.id
                  ? 'border-blue-500 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              <tab.icon className="h-4 w-4" />
              <span>{tab.label}</span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="min-h-96">
        {renderTabContent()}
      </div>
    </div>
  );
};

export default DomainWorkspace; 