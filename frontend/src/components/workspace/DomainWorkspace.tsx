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
  Trash2
} from 'lucide-react';
import Card, { CardHeader, CardTitle, CardContent } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { Domain, Document, SearchResult, AnalyticsMetrics, ConnectorConfig } from '../../types';
import { apiClient } from '../../utils/api';

interface DomainWorkspaceProps {
  domain: Domain;
  onEditDomain: () => void;
  onDeleteDomain: () => void;
}

type TabType = 'knowledge' | 'chat' | 'search' | 'sources' | 'analytics' | 'settings';

const DomainWorkspace: React.FC<DomainWorkspaceProps> = ({
  domain,
  onEditDomain,
  onDeleteDomain,
}) => {
  const [activeTab, setActiveTab] = useState<TabType>('knowledge');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [connectors, setConnectors] = useState<ConnectorConfig[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsMetrics | null>(null);
  const [loading, setLoading] = useState(false);

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
  }, [domain.id, activeTab]);

  const loadWorkspaceData = async () => {
    setLoading(true);
    try {
      switch (activeTab) {
        case 'knowledge':
          const docsResponse = await apiClient.getFiles(domain.id);
          if (docsResponse.success) {
            setDocuments(docsResponse.data);
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

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setLoading(true);
    try {
      const response = await apiClient.search({
        query: searchQuery,
        domainId: domain.id,
        filters: {},
        mode: 'hybrid',
        limit: 20,
        offset: 0,
      });
      
      if (response.success) {
        setSearchResults(response.data);
      }
    } catch (error) {
      console.error('Search failed:', error);
    } finally {
      setLoading(false);
    }
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
          <Button icon={<Upload className="h-4 w-4" />}>
            Upload Files
          </Button>
        </div>
      </div>

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
              {Math.round(documents.reduce((acc, d) => acc + d.size, 0) / 1024 / 1024)}MB
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
              <Button icon={<Upload className="h-4 w-4" />}>Upload Document</Button>
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
                        {(doc.size / 1024).toFixed(1)}KB • {new Date(doc.createdAt).toLocaleDateString()}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <span className={`px-2 py-1 text-xs font-medium rounded-full ${getStatusColor(doc.status)}`}>
                      {doc.status}
                    </span>
                    <Button variant="ghost" size="sm" icon={<Eye className="h-4 w-4" />} />
                    <Button variant="ghost" size="sm" icon={<Download className="h-4 w-4" />} />
                    <Button variant="ghost" size="sm" icon={<Trash2 className="h-4 w-4" />} />
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
          <p className="text-gray-600">Chat with the domain-specific AI assistant</p>
        </div>
      </div>

      <Card className="h-96">
        <CardContent className="h-full flex flex-col">
          <div className="flex-1 p-4 bg-gray-50 rounded-lg mb-4">
            <div className="text-center text-gray-500">
              <Brain className="h-12 w-12 mx-auto mb-2" />
              <p>Start a conversation with the AI assistant</p>
            </div>
          </div>
          <div className="flex space-x-2">
            <Input
              placeholder="Ask a question about this domain..."
              fullWidth
            />
            <Button icon={<MessageCircle className="h-4 w-4" />}>
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
              fullWidth
            />
            <Button onClick={handleSearch} loading={loading} icon={<Search className="h-4 w-4" />}>
              Search
            </Button>
          </div>
          
          <div className="flex space-x-4 text-sm">
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="rounded" />
              <span>Documents</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="rounded" />
              <span>Conversations</span>
            </label>
            <label className="flex items-center space-x-2">
              <input type="checkbox" className="rounded" />
              <span>External Data</span>
            </label>
          </div>
        </CardContent>
      </Card>

      {/* Search Results */}
      {searchResults.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Search Results ({searchResults.length})</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {searchResults.map((result) => (
                <div key={result.id} className="border-b border-gray-200 pb-4 last:border-b-0">
                  <h4 className="font-medium text-gray-900 mb-1">{result.title}</h4>
                  <p className="text-sm text-gray-600 mb-2">{result.snippet}</p>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>Confidence: {(result.confidence * 100).toFixed(1)}%</span>
                    <span>Score: {result.score.toFixed(2)}</span>
                  </div>
                </div>
              ))}
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