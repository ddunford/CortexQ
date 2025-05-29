import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/Card';
import Button from '../ui/Button';
import Input from '../ui/Input';
import { Modal } from '../ui/Modal';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../ui/Tabs';
import { api } from '../../utils/api';

interface WebScraperManagerProps {
  connector: {
    id: string;
    name: string;
    type: string;
    authConfig?: any;
    syncConfig?: any;
    mappingConfig?: any;
  };
  domainId: string;
  onConnectorUpdated?: (connector: any) => void;
}

interface DiscoveredUrls {
  sitemap_urls: string[];
  crawled_urls: string[];
  allowed_urls: string[];
  blocked_urls: string[];
  external_urls: string[];
  robots_blocked: string[];
  total_discovered: number;
  estimated_pages: number;
  discovery_method: string;
}

interface ConnectorConfig {
  start_urls: string;
  max_pages: number;
  max_depth: number;
  delay_ms: number;
  respect_robots: boolean;
  follow_external: boolean;
  include_patterns: string[];
  exclude_patterns: string[];
}

interface SyncJob {
  id: string;
  connector_id: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  records_processed: number;
  records_created: number;
  records_updated: number;
  error_message?: string;
  metadata?: any;
  created_at: string;
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
  recent_syncs: SyncJob[];
}

const WebScraperManager: React.FC<WebScraperManagerProps> = ({ connector, domainId, onConnectorUpdated }) => {
  const [config, setConfig] = useState<ConnectorConfig>({
    start_urls: '',
    max_pages: 50,
    max_depth: 3,
    delay_ms: 1000,
    respect_robots: true,
    follow_external: false,
    include_patterns: [],
    exclude_patterns: []
  });

  const [discoveredUrls, setDiscoveredUrls] = useState<DiscoveredUrls | null>(null);
  const [crawlStats, setCrawlStats] = useState<CrawlStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState('setup');
  const [showUrls, setShowUrls] = useState(false);

  // Load connector configuration on mount
  useEffect(() => {
    loadConnectorConfiguration();
  }, [connector.id]);

  const loadConnectorConfiguration = async () => {
    try {
      const connectorData = await api.getConnectorById(connector.id);
      if (connectorData?.auth_config) {
        setConfig({
          start_urls: connectorData.auth_config.start_urls || '',
          max_pages: connectorData.auth_config.max_pages || 50,
          max_depth: connectorData.auth_config.max_depth || 3,
          delay_ms: connectorData.auth_config.delay_ms || 1000,
          respect_robots: connectorData.auth_config.respect_robots !== false,
          follow_external: connectorData.auth_config.follow_external || false,
          include_patterns: connectorData.auth_config.include_patterns || [],
          exclude_patterns: connectorData.auth_config.exclude_patterns || []
        });
      }
      
      // Load discovered URLs if they exist
      await loadDiscoveredUrls();
    } catch (error) {
      console.error('Failed to load connector configuration:', error);
    }
  };

  const loadDiscoveredUrls = async (): Promise<DiscoveredUrls | null> => {
    try {
      const response = await api.getDiscoveredUrls(domainId, connector.id);
      if (response.success && response.data) {
        // The API returns { success: true, discovered_urls: {...} }
        // So we need to access response.data.discovered_urls
        const discoveredUrlsData = response.data.discovered_urls || response.data;
        setDiscoveredUrls(discoveredUrlsData);
        return discoveredUrlsData;
      }
      return null;
    } catch (err) {
      console.error('Failed to load discovered URLs:', err);
      return null;
    }
  };

  const loadCrawlStats = async (): Promise<CrawlStats | null> => {
    try {
      const response = await api.getSyncJobs(domainId, connector.id, { limit: 10 });
      if (response.success && response.data) {
        // Transform sync jobs data to match expected structure
        const syncJobs = response.data;
        const completedJobs = syncJobs.filter(job => job.status === 'completed');
        
        const crawlStats: CrawlStats = {
          crawl_stats: {
            total_pages: completedJobs.reduce((sum, job) => sum + (job.records_processed || 0), 0),
            successful_crawls: completedJobs.reduce((sum, job) => sum + (job.records_created || 0), 0),
            failed_crawls: syncJobs.filter(job => job.status === 'failed').length,
            success_rate: completedJobs.length / Math.max(syncJobs.length, 1),
            avg_word_count: 0, // Not available from sync jobs
            total_words: 0, // Not available from sync jobs
            first_crawl: syncJobs.length > 0 ? syncJobs[syncJobs.length - 1].created_at : undefined,
            last_crawl: syncJobs.length > 0 ? syncJobs[0].created_at : undefined,
          },
          recent_syncs: syncJobs
        };
        
        setCrawlStats(crawlStats);
        return crawlStats;
      }
      return null;
    } catch (err) {
      console.error('Failed to load sync jobs:', err);
      return null;
    }
  };

  const saveConfiguration = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      await api.updateConnectorById(connector.id, {
        auth_config: config
      });
      setSuccess('Configuration saved successfully!');
      if (onConnectorUpdated) {
        onConnectorUpdated(config);
      }
    } catch (err) {
      setError('Failed to save configuration: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const runUrlDiscovery = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await api.discoverUrls(domainId, connector.id);
      if (response.success) {
        setSuccess('URL discovery started! This may take a few moments...');
        
        // Poll for results
        const pollInterval = setInterval(async () => {
          try {
            const urlsData = await loadDiscoveredUrls();
            if (urlsData?.total_discovered > 0) {
              clearInterval(pollInterval);
              setActiveTab('preview');
              setSuccess(`Discovery completed! Found ${urlsData.total_discovered} URLs.`);
              setLoading(false);
            }
          } catch (error) {
            console.log('Still discovering...');
          }
        }, 3000);

        // Stop polling after 2 minutes
        setTimeout(() => {
          clearInterval(pollInterval);
          if (loading) {
            setLoading(false);
            setError('Discovery is taking longer than expected. Please check back later.');
          }
        }, 120000);
      }
    } catch (err) {
      setError('Failed to start URL discovery: ' + (err as Error).message);
      setLoading(false);
    }
  };

  const runScraping = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);

    try {
      const response = await api.scrapeDiscoveredUrls(domainId, connector.id);
      if (response.success) {
        setSuccess('Content scraping started! Check the ingestion status for progress.');
        setActiveTab('status');
      }
    } catch (err) {
      setError('Failed to start content scraping: ' + (err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = async () => {
    await loadConnectorConfiguration();
    await loadDiscoveredUrls();
    await loadCrawlStats();
  };

  // Load initial data
  useEffect(() => {
    refreshData();
  }, [connector.id, domainId]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold">Web Scraper Configuration</h2>
          <p className="text-gray-600">Configure and manage your web scraping connector</p>
        </div>
        <Button onClick={refreshData} variant="outline">
          Refresh
        </Button>
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-50 p-4 rounded-lg">
          {error}
        </div>
      )}

      {success && (
        <div className="bg-green-50 p-4 rounded-lg">
          {success}
        </div>
      )}

      {/* Main Content */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="setup">⚙️ Setup</TabsTrigger>
          <TabsTrigger value="preview">🔍 Preview URLs</TabsTrigger>
          <TabsTrigger value="status">📊 Status</TabsTrigger>
        </TabsList>

        {/* Setup Tab */}
        <TabsContent value="setup" className="space-y-6">
          <Card className="p-6">
            <h3 className="text-lg font-semibold mb-4">Scraper Configuration</h3>
            
            <div className="space-y-4">
              {/* Start URLs */}
              <div>
                <label className="block text-sm font-medium mb-2">
                  Start URLs (one per line) *
                </label>
                <textarea
                  value={config.start_urls}
                  onChange={(e) => setConfig({ ...config, start_urls: e.target.value })}
                  placeholder="https://example.com&#10;https://docs.example.com"
                  rows={4}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 resize-vertical"
                  required
                />
                <p className="text-sm text-gray-500 mt-1">
                  Enter the URLs where scraping should start
                </p>
              </div>

              {/* Basic Settings */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Max Pages</label>
                  <input
                    type="number"
                    value={config.max_pages}
                    onChange={(e) => setConfig({ ...config, max_pages: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="1000"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Max Depth</label>
                  <input
                    type="number"
                    value={config.max_depth}
                    onChange={(e) => setConfig({ ...config, max_depth: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1"
                    max="10"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Delay (ms)</label>
                  <input
                    type="number"
                    value={config.delay_ms}
                    onChange={(e) => setConfig({ ...config, delay_ms: parseInt(e.target.value) })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min="1000"
                    step="1000"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Settings</label>
                  <div className="space-y-2">
                    <label className="flex items-center space-x-2 text-sm">
                      <input
                        type="checkbox"
                        checked={config.respect_robots}
                        onChange={(e) => setConfig({ ...config, respect_robots: e.target.checked })}
                        className="rounded"
                      />
                      <span>Respect robots.txt</span>
                    </label>
                    <label className="flex items-center space-x-2 text-sm">
                      <input
                        type="checkbox"
                        checked={config.follow_external}
                        onChange={(e) => setConfig({ ...config, follow_external: e.target.checked })}
                        className="rounded"
                      />
                      <span>Follow external links</span>
                    </label>
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div className="flex space-x-4 pt-4">
                <Button 
                  onClick={saveConfiguration} 
                  disabled={loading || !config.start_urls.trim()}
                >
                  {loading ? 'Saving...' : 'Save Configuration'}
                </Button>

                <Button 
                  onClick={runUrlDiscovery} 
                  variant="outline"
                  disabled={loading || !config.start_urls.trim()}
                >
                  {loading ? 'Discovering...' : 'Discover URLs'}
                </Button>
              </div>
            </div>
          </Card>
        </TabsContent>

        {/* Preview URLs Tab */}
        <TabsContent value="preview" className="space-y-6">
          {discoveredUrls ? (
            <Card className="p-6">
              <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-semibold">Discovered URLs</h3>
                <Button onClick={loadDiscoveredUrls} variant="outline" size="sm">
                  Refresh
                </Button>
              </div>

              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-600">{discoveredUrls.allowed_urls?.length || discoveredUrls.total_discovered || 0}</div>
                  <div className="text-sm text-gray-600">Ready to Scrape</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-600">{discoveredUrls.sitemap_urls?.length || 0}</div>
                  <div className="text-sm text-gray-600">From Sitemap</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-orange-600">{discoveredUrls.blocked_urls?.length || 0}</div>
                  <div className="text-sm text-gray-600">Blocked</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-purple-600">{discoveredUrls.external_urls?.length || 0}</div>
                  <div className="text-sm text-gray-600">External</div>
                </div>
              </div>

              {/* Sample URLs */}
              <div className="space-y-4">
                <div className="flex justify-between items-center">
                  <h4 className="font-medium">Sample URLs to be scraped:</h4>
                  <Button 
                    onClick={() => setShowUrls(true)} 
                    variant="outline" 
                    size="sm"
                  >
                    View All URLs
                  </Button>
                </div>

                <div className="bg-gray-50 p-4 rounded-lg">
                  {discoveredUrls.allowed_urls?.slice(0, 10).map((url, index) => (
                    <div key={index} className="py-1 text-sm">
                      <a href={url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {url}
                      </a>
                    </div>
                  ))}
                  {discoveredUrls.allowed_urls?.length > 10 && (
                    <div className="text-sm text-gray-500 mt-2">
                      ... and {discoveredUrls.allowed_urls.length - 10} more URLs
                    </div>
                  )}
                </div>

                {/* Start Scraping */}
                <div className="pt-4">
                  <Button 
                    onClick={runScraping} 
                    disabled={loading || (!discoveredUrls.allowed_urls?.length && !discoveredUrls.total_discovered)}
                    className="w-full"
                  >
                    {loading ? 'Starting Scraping...' : `Start Scraping ${discoveredUrls.allowed_urls?.length || discoveredUrls.total_discovered || 0} URLs`}
                  </Button>
                </div>
              </div>
            </Card>
          ) : (
            <Card className="p-6 text-center">
              <h3 className="text-lg font-semibold mb-2">No URLs Discovered Yet</h3>
              <p className="text-gray-600 mb-4">
                Run URL discovery first to see what pages will be scraped.
              </p>
              <Button onClick={() => setActiveTab('setup')}>
                Go to Setup
              </Button>
            </Card>
          )}
        </TabsContent>

        {/* Status Tab */}
        <TabsContent value="status" className="space-y-6">
          <Card className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h3 className="text-lg font-semibold">Scraping Status</h3>
              <Button 
                onClick={refreshData}
                variant="outline"
                size="sm"
              >
                Refresh Status
              </Button>
            </div>
            
            <div className="space-y-6">
              {/* Discovery Results */}
              {discoveredUrls && (
                <div className="bg-gray-50 p-4 rounded-lg">
                  <h4 className="font-medium mb-3">🔍 URL Discovery Results</h4>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>Total URLs found: <span className="font-medium">{discoveredUrls.allowed_urls?.length || discoveredUrls.total_discovered || 0}</span></div>
                    <div>Discovery method: <span className="font-medium">{discoveredUrls.discovery_method}</span></div>
                    <div>Ready to scrape: <span className="font-medium text-green-600">{discoveredUrls.allowed_urls?.length || 0}</span></div>
                    <div>Blocked URLs: <span className="font-medium text-red-600">{discoveredUrls.blocked_urls?.length || 0}</span></div>
                  </div>
                </div>
              )}

              {/* Sync Jobs Status */}
              {crawlStats && crawlStats.recent_syncs && crawlStats.recent_syncs.length > 0 && (
                <div className="bg-blue-50 p-4 rounded-lg">
                  <h4 className="font-medium mb-3">📊 Recent Scraping Jobs</h4>
                  <div className="space-y-3">
                    {crawlStats.recent_syncs.slice(0, 3).map((job) => (
                      <div key={job.id} className="bg-white p-3 rounded border">
                        <div className="flex justify-between items-start mb-2">
                          <div className="text-sm font-medium">Job {job.id.slice(0, 8)}...</div>
                          <span className={`px-2 py-1 text-xs rounded-full ${
                            job.status === 'completed' 
                              ? 'bg-green-100 text-green-800' 
                              : job.status === 'failed'
                              ? 'bg-red-100 text-red-800'
                              : job.status === 'running'
                              ? 'bg-blue-100 text-blue-800'
                              : 'bg-gray-100 text-gray-800'
                          }`}>
                            {job.status}
                          </span>
                        </div>
                        
                        <div className="grid grid-cols-2 gap-2 text-sm text-gray-600">
                          {job.started_at && (
                            <div>Started: {new Date(job.started_at).toLocaleString()}</div>
                          )}
                          {job.completed_at && (
                            <div>Completed: {new Date(job.completed_at).toLocaleString()}</div>
                          )}
                          <div>Pages Processed: <span className="font-medium text-green-600">{job.records_processed || 0}</span></div>
                          {job.status === 'completed' && (
                            <div>Status: <span className="font-medium text-green-600">✅ Successfully completed</span></div>
                          )}
                        </div>
                        
                        {job.error_message && (
                          <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-sm text-red-700">
                            Error: {job.error_message}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Overall Crawl Statistics */}
              {crawlStats && crawlStats.crawl_stats && (
                <div className="bg-green-50 p-4 rounded-lg">
                  <h4 className="font-medium mb-3">📈 Overall Statistics</h4>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">{crawlStats.crawl_stats.total_pages}</div>
                      <div className="text-gray-600">Total Pages</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-blue-600">{crawlStats.crawl_stats.successful_crawls}</div>
                      <div className="text-gray-600">Successful</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-600">{crawlStats.crawl_stats.failed_crawls}</div>
                      <div className="text-gray-600">Failed</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-purple-600">{Math.round(crawlStats.crawl_stats.success_rate * 100)}%</div>
                      <div className="text-gray-600">Success Rate</div>
                    </div>
                  </div>
                  
                  {(crawlStats.crawl_stats.first_crawl || crawlStats.crawl_stats.last_crawl) && (
                    <div className="mt-4 pt-3 border-t border-green-200 grid grid-cols-2 gap-4 text-sm">
                      {crawlStats.crawl_stats.first_crawl && (
                        <div>First crawl: {new Date(crawlStats.crawl_stats.first_crawl).toLocaleString()}</div>
                      )}
                      {crawlStats.crawl_stats.last_crawl && (
                        <div>Last crawl: {new Date(crawlStats.crawl_stats.last_crawl).toLocaleString()}</div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* No Data State */}
              {!discoveredUrls && (!crawlStats || !crawlStats.recent_syncs || crawlStats.recent_syncs.length === 0) && (
                <div className="text-center py-8">
                  <p className="text-gray-600 mb-4">
                    No scraping activity found. Start by discovering URLs and then scraping content.
                  </p>
                  <Button onClick={() => setActiveTab('setup')}>
                    Go to Setup
                  </Button>
                </div>
              )}
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* URL List Modal */}
      <Modal open={showUrls} onOpenChange={setShowUrls}>
        <div className="max-w-4xl max-h-[80vh] overflow-auto">
          <h2 className="text-xl font-bold mb-4">All Discovered URLs</h2>
          
          {discoveredUrls && (
            <div className="space-y-4">
              {/* Allowed URLs */}
              <div>
                <h3 className="font-semibold text-green-600 mb-2">
                  ✅ Ready to Scrape ({discoveredUrls.allowed_urls?.length || 0})
                </h3>
                <div className="bg-green-50 p-3 rounded max-h-40 overflow-auto">
                  {discoveredUrls.allowed_urls?.map((url, index) => (
                    <div key={index} className="text-sm py-1">
                      <a href={url} target="_blank" rel="noopener noreferrer" className="text-green-700 hover:underline">
                        {url}
                      </a>
                    </div>
                  ))}
                </div>
              </div>

              {/* Blocked URLs */}
              {discoveredUrls.blocked_urls?.length > 0 && (
                <div>
                  <h3 className="font-semibold text-red-600 mb-2">
                    ❌ Blocked URLs ({discoveredUrls.blocked_urls.length})
                  </h3>
                  <div className="bg-red-50 p-3 rounded max-h-32 overflow-auto">
                    {discoveredUrls.blocked_urls.slice(0, 20).map((url, index) => (
                      <div key={index} className="text-sm py-1 text-red-700">{url}</div>
                    ))}
                    {discoveredUrls.blocked_urls.length > 20 && (
                      <div className="text-sm text-red-500">... and {discoveredUrls.blocked_urls.length - 20} more</div>
                    )}
                  </div>
                </div>
              )}

              {/* External URLs */}
              {discoveredUrls.external_urls?.length > 0 && (
                <div>
                  <h3 className="font-semibold text-purple-600 mb-2">
                    🔗 External URLs ({discoveredUrls.external_urls.length})
                  </h3>
                  <div className="bg-purple-50 p-3 rounded max-h-32 overflow-auto">
                    {discoveredUrls.external_urls.slice(0, 20).map((url, index) => (
                      <div key={index} className="text-sm py-1 text-purple-700">{url}</div>
                    ))}
                    {discoveredUrls.external_urls.length > 20 && (
                      <div className="text-sm text-purple-500">... and {discoveredUrls.external_urls.length - 20} more</div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className="flex justify-end mt-6">
            <Button onClick={() => setShowUrls(false)}>Close</Button>
          </div>
        </div>
      </Modal>
    </div>
  );
};

export default WebScraperManager; 