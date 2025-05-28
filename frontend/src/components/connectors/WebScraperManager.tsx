import React, { useState, useEffect } from 'react';
import { 
  Eye, 
  TestTube, 
  Settings, 
  Play, 
  BarChart3, 
  AlertCircle, 
  CheckCircle, 
  XCircle, 
  Clock, 
  Link,
  Globe,
  Shield,
  Download,
  Filter,
  RefreshCw
} from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import { Button } from '../ui/Button';
import { Input } from '../ui/Input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/Tabs';
import { apiClient } from '../../utils/api';
import { ConnectorConfig } from '../../types';

interface WebScraperManagerProps {
  connector: ConnectorConfig;
  domainId: string;
  onConnectorUpdated?: (connector: ConnectorConfig) => void;
}

interface CrawlPreview {
  preview: {
    discovered_urls: string[];
    allowed_urls: string[];
    blocked_urls: string[];
    robots_blocked: string[];
    external_urls: string[];
    estimated_pages: number;
    estimated_duration: string;
  };
  summary: {
    total_discovered: number;
    total_allowed: number;
    total_blocked: number;
    robots_blocked: number;
    external_urls: number;
  };
}

interface CrawlStats {
  crawl_stats: {
    total_pages: number;
    successful_crawls: number;
    failed_crawls: number;
    success_rate: number;
    avg_word_count: number;
    total_words: number;
    first_crawl?: string;
    last_crawl?: string;
  };
  recent_syncs: Array<{
    id: string;
    status: string;
    started_at?: string;
    completed_at?: string;
    records_processed: number;
    error_message?: string;
  }>;
}

interface CrawlRules {
  include_patterns: string[];
  exclude_patterns: string[];
  follow_external: boolean;
  respect_robots: boolean;
  max_file_size: number;
  custom_user_agent?: string;
  crawl_frequency_hours?: number;
  content_filters?: {
    min_word_count?: number;
    exclude_nav_elements?: boolean;
    exclude_footer_elements?: boolean;
    extract_metadata?: boolean;
  };
}

interface CrawledPage {
  id: string;
  url: string;
  title: string;
  status: string;
  word_count: number;
  content_hash: string;
  last_crawled: string;
  depth: number;
  content_type: string;
  file_size: number;
  error_message?: string;
  content_preview: string;
}

interface CrawledPagesResponse {
  pages: CrawledPage[];
  pagination: {
    current_page: number;
    page_size: number;
    total_pages: number;
    total_count: number;
    has_next: boolean;
    has_previous: boolean;
  };
  filters: {
    status_filter?: string;
    search_query?: string;
  };
}

interface PerformanceMetrics {
  pages_per_second: number;
  avg_response_time: number;
  error_rate: number;
  bandwidth_usage_mb: number;
  cache_hit_rate: number;
  robots_compliance_rate: number;
}

interface OptimizationSuggestion {
  type: string;
  severity: 'low' | 'medium' | 'high';
  message: string;
  recommended_action: string;
}

interface OptimizationData {
  current_metrics: PerformanceMetrics;
  suggestions: OptimizationSuggestion[];
  recommended_settings: Record<string, any>;
  optimization_score: number;
}

export const WebScraperManager: React.FC<WebScraperManagerProps> = ({
  connector,
  domainId,
  onConnectorUpdated
}) => {
  const [activeTab, setActiveTab] = useState('overview');
  const [loading, setLoading] = useState(false);
  const [preview, setPreview] = useState<CrawlPreview | null>(null);
  const [stats, setStats] = useState<CrawlStats | null>(null);
  const [testResult, setTestResult] = useState<any>(null);
  const [crawledPages, setCrawledPages] = useState<CrawledPagesResponse | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [optimizationData, setOptimizationData] = useState<OptimizationData | null>(null);
  const [scheduleStatus, setScheduleStatus] = useState<any>(null);
  const [crawlRules, setCrawlRules] = useState<CrawlRules>({
    include_patterns: connector.authConfig?.include_patterns || [],
    exclude_patterns: connector.authConfig?.exclude_patterns || [],
    follow_external: connector.authConfig?.follow_external || false,
    respect_robots: connector.authConfig?.respect_robots !== false, // Default true
    max_file_size: connector.authConfig?.max_file_size || 5242880, // 5MB
              custom_user_agent: connector.authConfig?.custom_user_agent || 'CortexQ-Bot/1.0',
    crawl_frequency_hours: connector.authConfig?.crawl_frequency_hours || 24,
    content_filters: {
      min_word_count: connector.authConfig?.content_filters?.min_word_count || 10,
      exclude_nav_elements: connector.authConfig?.content_filters?.exclude_nav_elements !== false,
      exclude_footer_elements: connector.authConfig?.content_filters?.exclude_footer_elements !== false,
      extract_metadata: connector.authConfig?.content_filters?.extract_metadata !== false,
    }
  });
  const [error, setError] = useState<string | null>(null);
  const [contentFilter, setContentFilter] = useState<{
    status?: 'success' | 'failed' | 'skipped';
    search?: string;
    page?: number;
  }>({});

  // Enhanced features state
  const [contentAnalytics, setContentAnalytics] = useState<any>(null);
  const [crawlSessionStatus, setCrawlSessionStatus] = useState<any>(null);
  const [qualityReport, setQualityReport] = useState<any>(null);
  const [duplicateAnalysis, setDuplicateAnalysis] = useState<any>(null);
  const [intelligentCrawlOptions, setIntelligentCrawlOptions] = useState({
    intelligent_discovery: true,
    real_time_monitoring: true,
    quality_threshold: 0.3,
    duplicate_threshold: 0.85,
    max_depth: connector.authConfig?.max_depth || 2,
    max_pages: connector.authConfig?.max_pages || 100
  });
  const [isIntelligentCrawlRunning, setIsIntelligentCrawlRunning] = useState(false);
  const [enhancedConfig, setEnhancedConfig] = useState({
    intelligent_discovery: connector.authConfig?.intelligent_discovery !== false,
    real_time_monitoring: connector.authConfig?.real_time_monitoring !== false,
    adaptive_scheduling: connector.authConfig?.adaptive_scheduling !== false,
    quality_threshold: connector.authConfig?.quality_threshold || 0.3,
    duplicate_threshold: connector.authConfig?.duplicate_threshold || 0.85,
    max_file_size: connector.authConfig?.max_file_size || 5242880,
    content_filters: {
      min_word_count: connector.authConfig?.content_filters?.min_word_count || 10,
      exclude_nav_elements: connector.authConfig?.content_filters?.exclude_nav_elements !== false,
      exclude_footer_elements: connector.authConfig?.content_filters?.exclude_footer_elements !== false,
      extract_metadata: connector.authConfig?.content_filters?.extract_metadata !== false,
    },
    crawl_frequency_hours: connector.authConfig?.crawl_frequency_hours || 24,
              custom_user_agent: connector.authConfig?.custom_user_agent || 'CortexQ-Bot/1.0'
  });

  useEffect(() => {
    if (activeTab === 'stats') {
      loadStats();
    } else if (activeTab === 'content') {
      loadCrawledPages();
    } else if (activeTab === 'performance') {
      loadPerformanceMetrics();
      loadOptimizationSuggestions();
    } else if (activeTab === 'analytics') {
      loadContentAnalytics();
    } else if (activeTab === 'quality') {
      loadQualityReport();
    } else if (activeTab === 'monitoring') {
      loadCrawlSessionStatus();
    } else if (activeTab === 'duplicates') {
      loadDuplicateAnalysis();
    }
  }, [activeTab]);

  const loadPreview = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.previewWebScraper(domainId, connector.id);
      if (response.success) {
        setPreview(response.data);
      } else {
        setError(response.message || 'Failed to load preview');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load preview');
    } finally {
      setLoading(false);
    }
  };

  const loadStats = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getWebScraperStats(domainId, connector.id);
      if (response.success) {
        setStats(response.data);
      } else {
        setError(response.message || 'Failed to load stats');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load stats');
    } finally {
      setLoading(false);
    }
  };

  const testConfiguration = async () => {
    setLoading(true);
    setError(null);
    setTestResult(null);
    try {
      const response = await apiClient.testWebScraperConfig(domainId, connector.id, {
        ...connector.authConfig,
        ...crawlRules
      });
      if (response.success) {
        setTestResult(response.data);
      } else {
        setError(response.message || 'Configuration test failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Configuration test failed');
    } finally {
      setLoading(false);
    }
  };

  const updateCrawlRules = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.updateCrawlRules(domainId, connector.id, crawlRules);
      if (response.success) {
        // Update local connector data
        const updatedConnector = {
          ...connector,
          authConfig: {
            ...connector.authConfig,
            ...response.data.updated_rules
          }
        };
        onConnectorUpdated?.(updatedConnector);
        setError('Crawl rules updated successfully!');
        // Clear success message after 3 seconds
        setTimeout(() => setError(null), 3000);
      } else {
        setError(response.message || 'Failed to update crawl rules');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update crawl rules');
    } finally {
      setLoading(false);
    }
  };

  const startSync = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.syncConnector(domainId, connector.id);
      if (response.success) {
        setError('Sync started successfully!');
        setTimeout(() => setError(null), 3000);
        // Refresh stats after starting sync
        if (activeTab === 'stats') {
          setTimeout(() => loadStats(), 2000);
        }
      } else {
        setError(response.message || 'Failed to start sync');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start sync');
    } finally {
      setLoading(false);
    }
  };

  const loadCrawledPages = async (filters?: typeof contentFilter) => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getCrawledPages(domainId, connector.id, {
        page: filters?.page || contentFilter.page || 1,
        page_size: 20,
        status_filter: filters?.status || contentFilter.status,
        search_query: filters?.search || contentFilter.search
      });
      if (response.success) {
        setCrawledPages(response.data);
      } else {
        setError(response.message || 'Failed to load crawled pages');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load crawled pages');
    } finally {
      setLoading(false);
    }
  };

  const deletePage = async (pageId: string) => {
    if (!confirm('Are you sure you want to delete this crawled page?')) return;
    
    setLoading(true);
    try {
      const response = await apiClient.deleteCrawledPage(domainId, connector.id, pageId);
      if (response.success) {
        // Reload the current page
        loadCrawledPages();
      } else {
        setError(response.message || 'Failed to delete page');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete page');
    } finally {
      setLoading(false);
    }
  };

  const handleContentFilterChange = (newFilters: Partial<typeof contentFilter>) => {
    const updatedFilters = { ...contentFilter, ...newFilters };
    setContentFilter(updatedFilters);
    loadCrawledPages(updatedFilters);
  };

  const loadPerformanceMetrics = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getWebScraperPerformanceMetrics(domainId, connector.id);
      if (response.success) {
        setPerformanceMetrics(response.data.metrics);
      } else {
        setError(response.message || 'Failed to load performance metrics');
      }
    } catch (error) {
      setError('Failed to load performance metrics');
    } finally {
      setLoading(false);
    }
  };

  const loadOptimizationSuggestions = async () => {
    setLoading(true);
    try {
      const response = await apiClient.getWebScraperOptimizationSuggestions(domainId, connector.id);
      if (response.success) {
        setOptimizationData(response.data);
      } else {
        setError(response.message || 'Failed to load optimization suggestions');
      }
    } catch (error) {
      setError('Failed to load optimization suggestions');
    } finally {
      setLoading(false);
    }
  };

  const applyOptimization = async () => {
    if (!optimizationData?.recommended_settings) return;
    
    setLoading(true);
    try {
      const response = await apiClient.applyWebScraperOptimization(
        domainId, 
        connector.id, 
        { recommended_settings: optimizationData.recommended_settings }
      );
      if (response.success) {
        // Refresh the connector data
        if (onConnectorUpdated) {
          // Trigger a refresh of the connector
          window.location.reload();
        }
        // Reload optimization data
        await loadOptimizationSuggestions();
      } else {
        setError(response.message || 'Failed to apply optimization');
      }
    } catch (error) {
      setError('Failed to apply optimization');
    } finally {
      setLoading(false);
    }
  };

  const scheduleCrawl = async () => {
    setLoading(true);
    try {
      const response = await apiClient.scheduleWebScraperCrawl(domainId, connector.id);
      if (response.success) {
        setScheduleStatus(response.data);
        // Refresh stats after scheduling
        if (response.data.status === 'completed') {
          await loadStats();
          await loadCrawledPages();
        }
      } else {
        setError(response.message || 'Failed to schedule crawl');
      }
    } catch (error) {
      setError('Failed to schedule crawl');
    } finally {
      setLoading(false);
    }
  };

  const formatDuration = (duration: string) => {
    return duration.replace(/(\d+\.?\d*)\s*(seconds?|minutes?|hours?)/, '$1 $2');
  };

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const renderOverview = () => (
    <div className="space-y-6">
      {/* Configuration Summary */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="h-5 w-5" />
            <span>Configuration</span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Start URLs</label>
              <div className="mt-1 text-sm text-gray-600">
                {connector.authConfig?.start_urls?.split(',').map((url: string, index: number) => (
                  <div key={index} className="flex items-center space-x-2">
                    <Link className="h-3 w-3" />
                    <span className="truncate">{url.trim()}</span>
                  </div>
                ))}
              </div>
            </div>
            <div>
              <label className="text-sm font-medium text-gray-700">Crawl Settings</label>
              <div className="mt-1 space-y-1 text-sm text-gray-600">
                <div>Max Depth: {connector.authConfig?.max_depth || 2}</div>
                <div>Max Pages: {connector.authConfig?.max_pages || 100}</div>
                <div>Delay: {connector.authConfig?.delay_ms || 1000}ms</div>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Button
          onClick={() => {
            setActiveTab('preview');
            loadPreview();
          }}
          className="flex items-center space-x-2 h-12"
          variant="outline"
        >
          <Eye className="h-4 w-4" />
          <span>Preview Crawl</span>
        </Button>
        
        <Button
          onClick={testConfiguration}
          className="flex items-center space-x-2 h-12"
          variant="outline"
          disabled={loading}
        >
          <TestTube className="h-4 w-4" />
          <span>Test Config</span>
        </Button>
        
        <Button
          onClick={startSync}
          className="flex items-center space-x-2 h-12"
          disabled={loading}
        >
          <Play className="h-4 w-4" />
          <span>Start Crawl</span>
        </Button>
      </div>

      {/* Test Result */}
      {testResult && (
        <Card>
          <CardContent className="pt-6">
            <div className={`flex items-center space-x-3 p-4 rounded-lg ${
              testResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'
            }`}>
              {testResult.success ? (
                <CheckCircle className="h-5 w-5" />
              ) : (
                <XCircle className="h-5 w-5" />
              )}
              <div>
                <div className="font-medium">
                  {testResult.success ? 'Configuration Valid' : 'Configuration Error'}
                </div>
                {testResult.result && (
                  <div className="text-sm mt-1">
                    {testResult.result.accessible_urls || 0} of {testResult.result.total_urls || 0} URLs accessible
                  </div>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  const renderPreview = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Crawl Preview</h3>
        <Button 
          onClick={loadPreview} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh Preview</span>
        </Button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {preview && (
        <div className="space-y-4">
          {/* Summary Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">{preview.summary.total_discovered}</div>
                <div className="text-sm text-gray-600">Discovered</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{preview.summary.total_allowed}</div>
                <div className="text-sm text-gray-600">Allowed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-red-600">{preview.summary.total_blocked}</div>
                <div className="text-sm text-gray-600">Blocked</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-orange-600">{preview.summary.robots_blocked}</div>
                <div className="text-sm text-gray-600">Robots.txt</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-purple-600">{preview.summary.external_urls}</div>
                <div className="text-sm text-gray-600">External</div>
              </CardContent>
            </Card>
          </div>

          {/* Estimation */}
          <Card>
            <CardContent className="p-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <Clock className="h-5 w-5 text-blue-600" />
                  <div>
                    <div className="font-medium">Estimated Crawl</div>
                    <div className="text-sm text-gray-600">
                      {preview.preview.estimated_pages} pages in {formatDuration(preview.preview.estimated_duration)}
                    </div>
                  </div>
                </div>
                <Button 
                  onClick={startSync}
                  disabled={loading || preview.summary.total_allowed === 0}
                  className="flex items-center space-x-2"
                >
                  <Play className="h-4 w-4" />
                  <span>Start Crawl</span>
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* URL Lists */}
          <Tabs defaultValue="allowed" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="allowed">Allowed URLs ({preview.summary.total_allowed})</TabsTrigger>
              <TabsTrigger value="blocked">Blocked URLs ({preview.summary.total_blocked})</TabsTrigger>
              <TabsTrigger value="robots">Robots.txt ({preview.summary.robots_blocked})</TabsTrigger>
              <TabsTrigger value="external">External ({preview.summary.external_urls})</TabsTrigger>
            </TabsList>

            <TabsContent value="allowed" className="mt-4">
              <Card>
                <CardContent className="p-4">
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {preview.preview.allowed_urls.length > 0 ? (
                      preview.preview.allowed_urls.map((url, index) => (
                        <div key={index} className="flex items-center space-x-2 text-sm">
                          <CheckCircle className="h-3 w-3 text-green-600 flex-shrink-0" />
                          <span className="truncate">{url}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-500 py-4">No allowed URLs found</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="blocked" className="mt-4">
              <Card>
                <CardContent className="p-4">
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {preview.preview.blocked_urls.length > 0 ? (
                      preview.preview.blocked_urls.map((url, index) => (
                        <div key={index} className="flex items-center space-x-2 text-sm">
                          <XCircle className="h-3 w-3 text-red-600 flex-shrink-0" />
                          <span className="truncate">{url}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-500 py-4">No blocked URLs</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="robots" className="mt-4">
              <Card>
                <CardContent className="p-4">
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {preview.preview.robots_blocked.length > 0 ? (
                      preview.preview.robots_blocked.map((url, index) => (
                        <div key={index} className="flex items-center space-x-2 text-sm">
                          <Shield className="h-3 w-3 text-orange-600 flex-shrink-0" />
                          <span className="truncate">{url}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-500 py-4">No robots.txt restrictions</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="external" className="mt-4">
              <Card>
                <CardContent className="p-4">
                  <div className="max-h-64 overflow-y-auto space-y-2">
                    {preview.preview.external_urls.length > 0 ? (
                      preview.preview.external_urls.map((url, index) => (
                        <div key={index} className="flex items-center space-x-2 text-sm">
                          <Globe className="h-3 w-3 text-purple-600 flex-shrink-0" />
                          <span className="truncate">{url}</span>
                        </div>
                      ))
                    ) : (
                      <div className="text-center text-gray-500 py-4">No external URLs found</div>
                    )}
                  </div>
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      )}

      {!preview && !loading && (
        <Card>
          <CardContent className="p-8 text-center">
            <Eye className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Preview Available</h3>
            <p className="text-gray-600 mb-4">Click "Refresh Preview" to see what URLs would be crawled.</p>
            <Button onClick={loadPreview} disabled={loading}>
              Load Preview
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );

  const renderContent = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Crawled Content</h3>
        <Button 
          onClick={() => loadCrawledPages()} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {/* Filters */}
      <Card>
        <CardContent className="p-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Status Filter
              </label>
              <select
                value={contentFilter.status || ''}
                onChange={(e) => handleContentFilterChange({ 
                  status: e.target.value as any || undefined, 
                  page: 1 
                })}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
              >
                <option value="">All Status</option>
                <option value="success">Success</option>
                <option value="failed">Failed</option>
                <option value="skipped">Skipped</option>
              </select>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Search Content
              </label>
              <Input
                placeholder="Search URLs, titles, or content..."
                value={contentFilter.search || ''}
                onChange={(e) => handleContentFilterChange({ 
                  search: e.target.value || undefined, 
                  page: 1 
                })}
                className="text-sm"
              />
            </div>

            <div className="flex items-end">
              <Button 
                onClick={() => {
                  setContentFilter({});
                  loadCrawledPages({});
                }}
                variant="outline"
                className="w-full"
              >
                Clear Filters
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Content List */}
      {crawledPages && (
        <div className="space-y-4">
          {/* Summary */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {crawledPages.pagination.total_count}
                </div>
                <div className="text-sm text-gray-600">Total Pages</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">
                  {crawledPages.pages.filter(p => p.status === 'success').length}
                </div>
                <div className="text-sm text-gray-600">Successful</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-red-600">
                  {crawledPages.pages.filter(p => p.status === 'failed').length}
                </div>
                <div className="text-sm text-gray-600">Failed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {Math.round(crawledPages.pages.reduce((acc, p) => acc + p.word_count, 0) / crawledPages.pages.length) || 0}
                </div>
                <div className="text-sm text-gray-600">Avg Words</div>
              </CardContent>
            </Card>
          </div>

          {/* Pages Table */}
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="border-b bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">URL</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Title</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Status</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Words</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Last Crawled</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {crawledPages.pages.map((page) => (
                      <tr key={page.id} className="border-b hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <div className="max-w-xs">
                            <a 
                              href={page.url} 
                              target="_blank" 
                              rel="noopener noreferrer"
                              className="text-blue-600 hover:text-blue-800 text-sm truncate block"
                              title={page.url}
                            >
                              {page.url}
                            </a>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <div className="max-w-xs">
                            <div className="font-medium text-sm truncate" title={page.title}>
                              {page.title || 'No title'}
                            </div>
                            <div className="text-xs text-gray-500 mt-1 truncate" title={page.content_preview}>
                              {page.content_preview}
                            </div>
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                            page.status === 'success' 
                              ? 'bg-green-100 text-green-800'
                              : page.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : 'bg-yellow-100 text-yellow-800'
                          }`}>
                            {page.status}
                          </span>
                          {page.error_message && (
                            <div className="text-xs text-red-600 mt-1" title={page.error_message}>
                              {page.error_message.substring(0, 50)}...
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {page.word_count.toLocaleString()}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-700">
                          {new Date(page.last_crawled).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-3">
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={() => deletePage(page.id)}
                            className="text-red-600 hover:text-red-800"
                          >
                            Delete
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              {crawledPages.pages.length === 0 && (
                <div className="text-center py-8 text-gray-500">
                  No crawled pages found
                </div>
              )}
            </CardContent>
          </Card>

          {/* Pagination */}
          {crawledPages.pagination.total_pages > 1 && (
            <div className="flex items-center justify-between">
              <div className="text-sm text-gray-700">
                Showing {((crawledPages.pagination.current_page - 1) * crawledPages.pagination.page_size) + 1} to{' '}
                {Math.min(crawledPages.pagination.current_page * crawledPages.pagination.page_size, crawledPages.pagination.total_count)} of{' '}
                {crawledPages.pagination.total_count} results
              </div>
              <div className="flex space-x-2">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!crawledPages.pagination.has_previous}
                  onClick={() => handleContentFilterChange({ page: crawledPages.pagination.current_page - 1 })}
                >
                  Previous
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={!crawledPages.pagination.has_next}
                  onClick={() => handleContentFilterChange({ page: crawledPages.pagination.current_page + 1 })}
                >
                  Next
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );

  const renderAdvancedSettings = () => (
    <div className="space-y-6">
      <h3 className="text-lg font-semibold">Advanced Configuration</h3>
      
      {/* User Agent Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Settings className="h-5 w-5" />
            <span>User Agent & Behavior</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Custom User Agent
            </label>
            <Input
              value={crawlRules.custom_user_agent || ''}
              onChange={(e) => setCrawlRules({
                ...crawlRules,
                custom_user_agent: e.target.value
              })}
                                    placeholder="CortexQ-Bot/1.0"
              className="text-sm"
            />
            <p className="text-xs text-gray-500 mt-1">
              How the crawler identifies itself to websites
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Crawl Frequency (hours)
            </label>
            <select
              value={crawlRules.crawl_frequency_hours || 24}
              onChange={(e) => setCrawlRules({
                ...crawlRules,
                crawl_frequency_hours: parseInt(e.target.value)
              })}
              className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm"
            >
              <option value={1}>Every hour</option>
              <option value={6}>Every 6 hours</option>
              <option value={12}>Every 12 hours</option>
              <option value={24}>Daily</option>
              <option value={168}>Weekly</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Content Filtering */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center space-x-2">
            <Filter className="h-5 w-5" />
            <span>Content Filtering</span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Minimum Word Count
            </label>
            <Input
              type="number"
              value={crawlRules.content_filters?.min_word_count || 10}
              onChange={(e) => setCrawlRules({
                ...crawlRules,
                content_filters: {
                  ...crawlRules.content_filters,
                  min_word_count: parseInt(e.target.value) || 10
                }
              })}
              className="text-sm"
              min="1"
              max="1000"
            />
            <p className="text-xs text-gray-500 mt-1">
              Skip pages with fewer words than this
            </p>
          </div>

          <div className="space-y-3">
            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={crawlRules.content_filters?.exclude_nav_elements !== false}
                onChange={(e) => setCrawlRules({
                  ...crawlRules,
                  content_filters: {
                    ...crawlRules.content_filters,
                    exclude_nav_elements: e.target.checked
                  }
                })}
                className="rounded"
              />
              <label className="text-sm text-gray-700">
                Exclude navigation elements
              </label>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={crawlRules.content_filters?.exclude_footer_elements !== false}
                onChange={(e) => setCrawlRules({
                  ...crawlRules,
                  content_filters: {
                    ...crawlRules.content_filters,
                    exclude_footer_elements: e.target.checked
                  }
                })}
                className="rounded"
              />
              <label className="text-sm text-gray-700">
                Exclude footer elements
              </label>
            </div>

            <div className="flex items-center space-x-2">
              <input
                type="checkbox"
                checked={crawlRules.content_filters?.extract_metadata !== false}
                onChange={(e) => setCrawlRules({
                  ...crawlRules,
                  content_filters: {
                    ...crawlRules.content_filters,
                    extract_metadata: e.target.checked
                  }
                })}
                className="rounded"
              />
              <label className="text-sm text-gray-700">
                Extract page metadata
              </label>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Save Settings */}
      <div className="flex justify-end">
        <Button
          onClick={updateCrawlRules}
          disabled={loading}
          className="flex items-center space-x-2"
        >
          <Settings className="h-4 w-4" />
          <span>Save Settings</span>
        </Button>
      </div>
    </div>
  );

  const renderStats = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Crawl Statistics</h3>
        <Button 
          onClick={loadStats} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      )}

      {stats && (
        <div className="space-y-6">
          {/* Overview Stats */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">{stats.crawl_stats.total_pages}</div>
                <div className="text-sm text-gray-600">Total Pages</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">{stats.crawl_stats.successful_crawls}</div>
                <div className="text-sm text-gray-600">Successful</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-red-600">{stats.crawl_stats.failed_crawls}</div>
                <div className="text-sm text-gray-600">Failed</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-purple-600">{stats.crawl_stats.success_rate.toFixed(1)}%</div>
                <div className="text-sm text-gray-600">Success Rate</div>
              </CardContent>
            </Card>
          </div>

          {/* Detailed Stats */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Content Statistics</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total Words:</span>
                    <span className="font-medium">{stats.crawl_stats.total_words.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Avg Words/Page:</span>
                    <span className="font-medium">{Math.round(stats.crawl_stats.avg_word_count).toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">First Crawl:</span>
                    <span className="font-medium">{formatDate(stats.crawl_stats.first_crawl)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Last Crawl:</span>
                    <span className="font-medium">{formatDate(stats.crawl_stats.last_crawl)}</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Recent Sync Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3 max-h-48 overflow-y-auto">
                  {stats.recent_syncs.length > 0 ? (
                    stats.recent_syncs.map((sync) => (
                      <div key={sync.id} className="flex items-center justify-between p-2 bg-gray-50 rounded">
                        <div className="flex items-center space-x-2">
                          {sync.status === 'completed' ? (
                            <CheckCircle className="h-4 w-4 text-green-600" />
                          ) : sync.status === 'failed' ? (
                            <XCircle className="h-4 w-4 text-red-600" />
                          ) : (
                            <Clock className="h-4 w-4 text-yellow-600" />
                          )}
                          <span className="text-sm font-medium capitalize">{sync.status}</span>
                        </div>
                        <div className="text-xs text-gray-500">
                          {formatDate(sync.completed_at || sync.started_at)}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center text-gray-500 py-4">No sync jobs yet</div>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      )}

      {!stats && !loading && (
        <Card>
          <CardContent className="p-8 text-center">
            <BarChart3 className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-900 mb-2">No Statistics Available</h3>
            <p className="text-gray-600 mb-4">Run a crawl to see statistics and performance data.</p>
            <Button onClick={startSync} disabled={loading}>
              Start First Crawl
            </Button>
          </CardContent>
        </Card>
      )}
    </div>
  );

  // Enhanced loading methods
  const loadContentAnalytics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getWebScraperContentAnalytics(domainId, connector.id);
      if (response.success) {
        setContentAnalytics(response.data);
      } else {
        setError(response.message || 'Failed to load content analytics');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load content analytics');
    } finally {
      setLoading(false);
    }
  };

  const loadCrawlSessionStatus = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getCrawlSessionStatus(domainId, connector.id);
      if (response.success) {
        setCrawlSessionStatus(response.data);
      } else {
        setError(response.message || 'Failed to load session status');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load session status');
    } finally {
      setLoading(false);
    }
  };

  const loadQualityReport = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getContentQualityReport(domainId, connector.id);
      if (response.success) {
        setQualityReport(response.data);
      } else {
        setError(response.message || 'Failed to load quality report');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load quality report');
    } finally {
      setLoading(false);
    }
  };

  const loadDuplicateAnalysis = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.getDuplicateContentAnalysis(domainId, connector.id);
      if (response.success) {
        setDuplicateAnalysis(response.data);
      } else {
        setError(response.message || 'Failed to load duplicate analysis');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load duplicate analysis');
    } finally {
      setLoading(false);
    }
  };

  const startIntelligentCrawl = async () => {
    setIsIntelligentCrawlRunning(true);
    setError(null);
    try {
      const response = await apiClient.startIntelligentCrawl(domainId, connector.id, intelligentCrawlOptions);
      if (response.success) {
        // Start polling for session status
        const pollInterval = setInterval(async () => {
          const statusResponse = await apiClient.getCrawlSessionStatus(domainId, connector.id);
          if (statusResponse.success) {
            setCrawlSessionStatus(statusResponse.data);
            if (statusResponse.data.status === 'inactive') {
              clearInterval(pollInterval);
              setIsIntelligentCrawlRunning(false);
              // Refresh other data
              loadStats();
              loadCrawledPages();
              loadContentAnalytics();
            }
          }
        }, 5000); // Poll every 5 seconds

        // Stop polling after 30 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          setIsIntelligentCrawlRunning(false);
        }, 30 * 60 * 1000);

      } else {
        setError(response.message || 'Failed to start intelligent crawl');
        setIsIntelligentCrawlRunning(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start intelligent crawl');
      setIsIntelligentCrawlRunning(false);
    }
  };

  const updateEnhancedConfig = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await apiClient.updateEnhancedWebScraperConfig(domainId, connector.id, enhancedConfig);
      if (response.success) {
        // Update connector config if callback is provided
        if (onConnectorUpdated) {
          const updatedConnector = { ...connector };
          updatedConnector.authConfig = { ...updatedConnector.authConfig, ...response.data.updated_config };
          onConnectorUpdated(updatedConnector);
        }
      } else {
        setError(response.message || 'Failed to update enhanced configuration');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to update enhanced configuration');
    } finally {
      setLoading(false);
    }
  };

  const renderPerformance = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Performance & Optimization</h3>
        <Button 
          onClick={() => {
            loadPerformanceMetrics();
            loadOptimizationSuggestions();
          }} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {performanceMetrics && (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-blue-600">
                {performanceMetrics.pages_per_second.toFixed(2)}
              </div>
              <div className="text-sm text-gray-600">Pages/Second</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-green-600">
                {(performanceMetrics.error_rate * 100).toFixed(1)}%
              </div>
              <div className="text-sm text-gray-600">Error Rate</div>
            </CardContent>
          </Card>
          <Card>
            <CardContent className="p-4 text-center">
              <div className="text-2xl font-bold text-purple-600">
                {performanceMetrics.avg_response_time.toFixed(2)}s
              </div>
              <div className="text-sm text-gray-600">Avg Response</div>
            </CardContent>
          </Card>
        </div>
      )}

      {optimizationData && (
        <Card>
          <CardHeader>
            <CardTitle>Optimization Suggestions</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span>Optimization Score:</span>
                <span className="font-bold text-lg">
                  {(optimizationData.optimization_score * 100).toFixed(0)}%
                </span>
              </div>
              
              {optimizationData.suggestions.map((suggestion, index) => (
                <div key={index} className={`p-3 rounded border-l-4 ${
                  suggestion.severity === 'high' ? 'border-red-500 bg-red-50' :
                  suggestion.severity === 'medium' ? 'border-yellow-500 bg-yellow-50' :
                  'border-blue-500 bg-blue-50'
                }`}>
                  <div className="font-medium">{suggestion.message}</div>
                  <div className="text-sm text-gray-600 mt-1">
                    Recommended: {suggestion.recommended_action}
                  </div>
                </div>
              ))}

              {Object.keys(optimizationData.recommended_settings).length > 0 && (
                <Button onClick={applyOptimization} disabled={loading} className="w-full">
                  Apply Optimization Settings
                </Button>
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );

  const renderQualityReport = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Content Quality Report</h3>
        <Button 
          onClick={loadQualityReport} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {qualityReport && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {qualityReport.report.total_pages}
                </div>
                <div className="text-sm text-gray-600">Total Pages</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">
                  {qualityReport.report.average_quality_score.toFixed(2)}
                </div>
                <div className="text-sm text-gray-600">Avg Quality</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-purple-600">
                  {qualityReport.report.quality_distribution.excellent}
                </div>
                <div className="text-sm text-gray-600">Excellent</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {qualityReport.report.quality_distribution.poor}
                </div>
                <div className="text-sm text-gray-600">Poor Quality</div>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Quality Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {qualityReport.report.recommendations.map((rec, index) => (
                  <div key={index} className="p-3 bg-gray-50 rounded">
                    <div className="font-medium">{rec.message}</div>
                    <div className="text-sm text-gray-600 mt-1">
                      Action: {rec.action}
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {qualityReport.top_pages && qualityReport.top_pages.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Top Quality Pages</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {qualityReport.top_pages.slice(0, 10).map((page, index) => (
                    <div key={index} className="p-3 border rounded">
                      <div className="flex items-center justify-between">
                        <div className="flex-1">
                          <div className="font-medium truncate">{page.title}</div>
                          <div className="text-sm text-gray-600 truncate">{page.url}</div>
                        </div>
                        <div className="text-right">
                          <div className="font-bold text-green-600">
                            {page.quality_score.toFixed(2)}
                          </div>
                          <div className="text-sm text-gray-600">
                            {page.word_count} words
                          </div>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );

  const renderRealTimeMonitoring = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Real-Time Monitoring</h3>
        <div className="flex space-x-2">
          <Button 
            onClick={loadCrawlSessionStatus} 
            disabled={loading}
            variant="outline"
            size="sm"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          </Button>
          <Button 
            onClick={startIntelligentCrawl}
            disabled={isIntelligentCrawlRunning}
            className="flex items-center space-x-2"
          >
            <Play className="h-4 w-4" />
            <span>Start Intelligent Crawl</span>
          </Button>
        </div>
      </div>

      {crawlSessionStatus && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center space-x-2">
                <div className={`w-3 h-3 rounded-full ${
                  crawlSessionStatus.status === 'active' ? 'bg-green-500' : 'bg-gray-400'
                }`}></div>
                <span>Crawl Session Status</span>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {crawlSessionStatus.session ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div>
                    <div className="text-sm text-gray-600">Pages Processed</div>
                    <div className="text-lg font-bold">
                      {crawlSessionStatus.session.pages_processed}
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">Success Rate</div>
                    <div className="text-lg font-bold text-green-600">
                      {(crawlSessionStatus.session.success_rate * 100).toFixed(1)}%
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">Avg Response</div>
                    <div className="text-lg font-bold">
                      {crawlSessionStatus.session.avg_response_time.toFixed(2)}s
                    </div>
                  </div>
                  <div>
                    <div className="text-sm text-gray-600">Queue Size</div>
                    <div className="text-lg font-bold">
                      {crawlSessionStatus.session.current_queue_size}
                    </div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-500 py-4">
                  No active crawl session
                </div>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Intelligent Crawl Options</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Quality Threshold
                  </label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="1"
                    value={intelligentCrawlOptions.quality_threshold}
                    onChange={(e) => setIntelligentCrawlOptions({
                      ...intelligentCrawlOptions,
                      quality_threshold: parseFloat(e.target.value)
                    })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Max Pages
                  </label>
                  <Input
                    type="number"
                    min="1"
                    max="1000"
                    value={intelligentCrawlOptions.max_pages}
                    onChange={(e) => setIntelligentCrawlOptions({
                      ...intelligentCrawlOptions,
                      max_pages: parseInt(e.target.value)
                    })}
                  />
                </div>
              </div>
              
              <div className="space-y-3 mt-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={intelligentCrawlOptions.intelligent_discovery}
                    onChange={(e) => setIntelligentCrawlOptions({
                      ...intelligentCrawlOptions,
                      intelligent_discovery: e.target.checked
                    })}
                    className="rounded"
                  />
                  <label className="text-sm text-gray-700">
                    Intelligent URL Discovery
                  </label>
                </div>
                <div className="flex items-center space-x-2">
                  <input
                    type="checkbox"
                    checked={intelligentCrawlOptions.real_time_monitoring}
                    onChange={(e) => setIntelligentCrawlOptions({
                      ...intelligentCrawlOptions,
                      real_time_monitoring: e.target.checked
                    })}
                    className="rounded"
                  />
                  <label className="text-sm text-gray-700">
                    Real-Time Monitoring
                  </label>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );

  const renderDuplicateAnalysis = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">Duplicate Content Analysis</h3>
        <Button 
          onClick={loadDuplicateAnalysis} 
          disabled={loading}
          variant="outline"
          className="flex items-center space-x-2"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
          <span>Refresh</span>
        </Button>
      </div>

      {duplicateAnalysis && (
        <div className="space-y-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-blue-600">
                  {duplicateAnalysis.analysis.total_pages}
                </div>
                <div className="text-sm text-gray-600">Total Pages</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-green-600">
                  {duplicateAnalysis.analysis.unique_pages}
                </div>
                <div className="text-sm text-gray-600">Unique Pages</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-red-600">
                  {duplicateAnalysis.analysis.exact_duplicates}
                </div>
                <div className="text-sm text-gray-600">Duplicates</div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="p-4 text-center">
                <div className="text-2xl font-bold text-orange-600">
                  {(duplicateAnalysis.analysis.duplication_rate * 100).toFixed(1)}%
                </div>
                <div className="text-sm text-gray-600">Duplication Rate</div>
              </CardContent>
            </Card>
          </div>

          {duplicateAnalysis.analysis.duplicate_groups.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Duplicate Groups</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {duplicateAnalysis.analysis.duplicate_groups.slice(0, 5).map((group, index) => (
                    <div key={index} className="p-3 border rounded">
                      <div className="flex items-center justify-between mb-2">
                        <span className="font-medium">
                          {group.duplicate_count} similar pages
                        </span>
                        <span className="text-sm text-gray-600">
                          {group.similarity_type}
                        </span>
                      </div>
                      <div className="space-y-2">
                        {group.pages.slice(0, 3).map((page, pageIndex) => (
                          <div key={pageIndex} className="text-sm">
                            <div className="font-medium truncate">{page.title}</div>
                            <div className="text-gray-600 truncate">{page.url}</div>
                          </div>
                        ))}
                        {group.pages.length > 3 && (
                          <div className="text-sm text-gray-500">
                            ... and {group.pages.length - 3} more
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {duplicateAnalysis.recommendations.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle>Recommendations</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  {duplicateAnalysis.recommendations.map((rec, index) => (
                    <div key={index} className="p-3 bg-gray-50 rounded">
                      <div className="font-medium">{rec.message}</div>
                      <div className="text-sm text-gray-600 mt-1">
                        Action: {rec.action}
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      )}
    </div>
  );

  return (
    <div className="space-y-6">
      {error && (
        <div className={`p-4 rounded-lg flex items-center space-x-3 ${
          error.includes('successfully') 
            ? 'bg-green-50 text-green-800 border border-green-200' 
            : 'bg-red-50 text-red-800 border border-red-200'
        }`}>
          {error.includes('successfully') ? (
            <CheckCircle className="h-5 w-5" />
          ) : (
            <AlertCircle className="h-5 w-5" />
          )}
          <span>{error}</span>
        </div>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} defaultValue="overview" className="w-full">
        <TabsList className="grid w-full grid-cols-9">
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="preview">Preview</TabsTrigger>
          <TabsTrigger value="content">Content</TabsTrigger>
          <TabsTrigger value="settings">Settings</TabsTrigger>
          <TabsTrigger value="performance">Performance</TabsTrigger>
          <TabsTrigger value="stats">Analytics</TabsTrigger>
          <TabsTrigger value="quality">Quality</TabsTrigger>
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
          <TabsTrigger value="duplicates">Duplicates</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="mt-6">
          {renderOverview()}
        </TabsContent>

        <TabsContent value="preview" className="mt-6">
          {renderPreview()}
        </TabsContent>

        <TabsContent value="content" className="mt-6">
          {renderContent()}
        </TabsContent>

        <TabsContent value="settings" className="mt-6">
          {renderAdvancedSettings()}
        </TabsContent>

        <TabsContent value="performance" className="mt-6">
          {renderPerformance()}
        </TabsContent>

        <TabsContent value="stats" className="mt-6">
          {renderStats()}
        </TabsContent>

        <TabsContent value="quality" className="mt-6">
          {renderQualityReport()}
        </TabsContent>

        <TabsContent value="monitoring" className="mt-6">
          {renderRealTimeMonitoring()}
        </TabsContent>

        <TabsContent value="duplicates" className="mt-6">
          {renderDuplicateAnalysis()}
        </TabsContent>
      </Tabs>
    </div>
  );
}; 