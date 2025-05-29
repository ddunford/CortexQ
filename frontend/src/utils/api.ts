import { 
  User, 
  Organization, 
  Domain, 
  DomainTemplate, 
  Message, 
  Document, 
  SearchQuery, 
  SearchResult, 
  AnalyticsMetrics,
  ConnectorConfig,
  ApiResponse 
} from '../types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api';

class ApiClient {
  private token: string | null = null;

  constructor() {
    if (typeof window !== 'undefined') {
      // Check for old token key first for backward compatibility
      this.token = localStorage.getItem('cortexq_token') || localStorage.getItem('rag_token');
      
      // If we found an old token, migrate it to the new key
      if (this.token && localStorage.getItem('rag_token')) {
        localStorage.setItem('cortexq_token', this.token);
        localStorage.removeItem('rag_token');
      }
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('cortexq_token', token);
      // Clean up old key if it exists
      localStorage.removeItem('rag_token');
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('cortexq_token');
      localStorage.removeItem('rag_token'); // Clean up old key too
    }
  }

  private onUnauthorized: (() => void) | null = null;

  setUnauthorizedHandler(handler: () => void) {
    this.onUnauthorized = handler;
  }

  private async request<T>(
    endpoint: string, 
    options: RequestInit = {}
  ): Promise<ApiResponse<T>> {
    const url = `${API_BASE_URL}${endpoint}`;
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> || {}),
    };

    // Only set Content-Type for non-FormData requests
    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
        signal: AbortSignal.timeout(30000),
      });

      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
        try {
          const errorData = await response.json();
          if (errorData.detail) {
            errorMessage = errorData.detail;
          } else if (errorData.message) {
            errorMessage = errorData.message;
          }
        } catch {
          // If we can't parse the error response, use the status text
        }

        if (response.status === 401) {
          this.clearToken();
          errorMessage = 'Authentication failed. Please log in again.';
          // Trigger unauthorized handler to redirect to login
          if (this.onUnauthorized) {
            this.onUnauthorized();
          }
        } else if (response.status === 403) {
          errorMessage = 'Access denied. You don\'t have permission for this action.';
        } else if (response.status === 404) {
          errorMessage = 'Resource not found.';
        } else if (response.status >= 500) {
          errorMessage = 'Server error. Please try again later.';
        }

        return {
          data: null as any,
          success: false,
          message: errorMessage,
        };
      }

      const data = await response.json();
      return {
        data,
        success: true,
      };
    } catch (error) {
      console.error('API request failed:', error);
      
      let errorMessage = 'Unknown error occurred';
      
      if (error instanceof TypeError && error.message.includes('fetch')) {
        errorMessage = 'Connection failed. Please check your internet connection or VPN.';
      } else if (error instanceof DOMException && error.name === 'AbortError') {
        errorMessage = 'Request timed out. Please try again.';
      } else if (error instanceof Error) {
        errorMessage = error.message;
      }

      return {
        data: null as any,
        success: false,
        message: errorMessage,
      };
    }
  }

  // Authentication APIs
  async login(email: string, password: string): Promise<ApiResponse<{ access_token: string; user: User }>> {
    return this.request('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
  }

  async register(userData: {
    email: string;
    password: string;
    full_name?: string;
  }): Promise<ApiResponse<{ access_token: string; user: User }>> {
    return this.request('/auth/register', {
      method: 'POST',
      body: JSON.stringify(userData),
    });
  }

  async getCurrentUser(): Promise<ApiResponse<User>> {
    return this.request('/users/me');
  }

  // Organization APIs
  async getOrganizations(): Promise<ApiResponse<Organization[]>> {
    return this.request('/organizations');
  }

  async getOrganization(id: string): Promise<ApiResponse<Organization>> {
    return this.request(`/organizations/${id}`);
  }

  async createOrganization(data: Partial<Organization>): Promise<ApiResponse<Organization>> {
    return this.request('/organizations', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateOrganization(id: string, data: Partial<Organization>): Promise<ApiResponse<Organization>> {
    return this.request(`/organizations/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // Domain APIs
  async getDomains(organizationId: string): Promise<ApiResponse<Domain[]>> {
    return this.request(`/organizations/${organizationId}/domains`);
  }

  async getDomain(id: string): Promise<ApiResponse<Domain>> {
    return this.request(`/domains/${id}`);
  }

  async createDomain(organizationId: string, data: Partial<Domain>): Promise<ApiResponse<Domain>> {
    return this.request(`/organizations/${organizationId}/domains`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateDomain(id: string, data: Partial<Domain>): Promise<ApiResponse<Domain>> {
    return this.request(`/domains/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteDomain(id: string): Promise<ApiResponse<void>> {
    return this.request(`/domains/${id}`, {
      method: 'DELETE',
    });
  }

  // Domain Templates APIs
  async getDomainTemplates(): Promise<ApiResponse<DomainTemplate[]>> {
    return this.request('/domain-templates');
  }

  async getDomainTemplate(id: string): Promise<ApiResponse<DomainTemplate>> {
    return this.request(`/domain-templates/${id}`);
  }

  // Chat APIs
  async sendMessage(data: {
    message: string;
    domainId?: string;
    sessionId?: string;
  }): Promise<ApiResponse<Message>> {
    return this.request('/chat', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async getChatSessions(domainId?: string): Promise<ApiResponse<any[]>> {
    const endpoint = domainId ? `/chat/sessions?domain=${domainId}` : '/chat/sessions';
    return this.request(endpoint);
  }

  async getChatSession(sessionId: string): Promise<ApiResponse<any>> {
    return this.request(`/chat/sessions/${sessionId}`);
  }

  async createChatSession(domainId: string): Promise<ApiResponse<any>> {
    return this.request('/chat/sessions', {
      method: 'POST',
      body: JSON.stringify({ domainId }),
    });
  }

  // File Management APIs
  async uploadFile(file: File, domainId: string): Promise<ApiResponse<Document>> {
    // Validate file before upload
    if (file.size === 0) {
      throw new Error('File is empty and cannot be uploaded');
    }
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('domain', domainId);

    return this.request('/files/upload', {
      method: 'POST',
      body: formData,
    });
  }

  async getFiles(domainId?: string): Promise<ApiResponse<{ files: Document[]; total: number }>> {
    const endpoint = domainId ? `/files?domain=${domainId}` : '/files';
    return this.request(endpoint);
  }

  async getFile(id: string): Promise<ApiResponse<Document>> {
    return this.request(`/files/${id}`);
  }

  async deleteFile(id: string): Promise<ApiResponse<void>> {
    return this.request(`/files/${id}`, {
      method: 'DELETE',
    });
  }

  async downloadFile(id: string): Promise<ApiResponse<{ download_url: string; filename: string; content_type: string; expires_in: number }>> {
    return this.request(`/files/${id}/download`);
  }

  async getProcessingStatus(domainId?: string): Promise<ApiResponse<any>> {
    const params = domainId ? `?domain=${domainId}` : '';
    return this.request(`/files/processing-status${params}`);
  }

  async reindexFiles(domainId: string, force: boolean = false): Promise<ApiResponse<any>> {
    return this.request('/files/reindex', {
      method: 'POST',
      body: JSON.stringify({ domain: domainId, force }),
    });
  }

  // Search APIs
  async search(query: SearchQuery): Promise<ApiResponse<any>> {
    // Convert frontend SearchQuery to backend SearchRequest format
    const searchRequest = {
      query: query.query,
      domain: query.domainId ? undefined : undefined, // Will be determined by backend
      domains: query.domainId ? [query.domainId] : undefined,
      filters: query.filters || {},
      mode: query.mode || 'hybrid',
      limit: query.limit || 20,
      offset: query.offset || 0,
      min_confidence: query.filters?.confidence || 0.3,
      include_content_types: query.filters?.documentTypes,
      exclude_content_types: undefined
    };

    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify(searchRequest),
    });
  }

  async getSearchSuggestions(query: string, domainId?: string): Promise<ApiResponse<string[]>> {
    const params = new URLSearchParams({ query });
    if (domainId) params.append('domain_id', domainId);
    return this.request(`/search/suggestions?${params}`);
  }

  // Analytics APIs
  async getAnalytics(domainId?: string, timeRange?: string): Promise<ApiResponse<AnalyticsMetrics>> {
    const params = new URLSearchParams();
    if (domainId) params.append('domain_id', domainId);
    if (timeRange) params.append('time_range', timeRange);
    
    const endpoint = `/analytics${params.toString() ? `?${params}` : ''}`;
    return this.request(endpoint);
  }

  async getClassificationAnalytics(): Promise<ApiResponse<any>> {
    return this.request('/analytics/classification');
  }

  async getRagAnalytics(): Promise<ApiResponse<any>> {
    return this.request('/analytics/rag');
  }

  async getAuditAnalytics(): Promise<ApiResponse<any>> {
    return this.request('/analytics/audit');
  }

  // Data Source Integration APIs
  async getConnectors(domainId: string): Promise<ApiResponse<ConnectorConfig[]>> {
    return this.request(`/domains/${domainId}/connectors`);
  }

  async getConnector(domainId: string, connectorId: string): Promise<ApiResponse<ConnectorConfig>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}`);
  }

  // Simple getConnector method for just connector ID
  async getConnectorById(connectorId: string): Promise<ApiResponse<ConnectorConfig>> {
    return this.request(`/connectors/${connectorId}`);
  }

  async createConnector(domainId: string, data: Partial<ConnectorConfig>): Promise<ApiResponse<ConnectorConfig>> {
    return this.request(`/domains/${domainId}/connectors`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateConnector(domainId: string, connectorId: string, data: Partial<ConnectorConfig>): Promise<ApiResponse<ConnectorConfig>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  // Simple updateConnector method for just connector ID
  async updateConnectorById(connectorId: string, data: Partial<ConnectorConfig>): Promise<ApiResponse<ConnectorConfig>> {
    return this.request(`/connectors/${connectorId}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteConnector(domainId: string, connectorId: string): Promise<ApiResponse<void>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}`, {
      method: 'DELETE',
    });
  }

  async testConnector(domainId: string, connectorId: string): Promise<ApiResponse<any>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/test`, {
      method: 'POST',
    });
  }

  async syncConnector(domainId: string, connectorId: string): Promise<ApiResponse<any>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/sync`, {
      method: 'POST',
    });
  }

  // Two-phase web scraper APIs
  async discoverUrls(domainId: string, connectorId: string): Promise<ApiResponse<any>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/discover-urls`, {
      method: 'POST',
    });
  }

  async scrapeDiscoveredUrls(domainId: string, connectorId: string): Promise<ApiResponse<any>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/scrape-urls`, {
      method: 'POST',
    });
  }

  async getDiscoveredUrls(domainId: string, connectorId: string): Promise<ApiResponse<any>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/discovered-urls`);
  }

  // Health Check APIs
  async getHealthStatus(): Promise<ApiResponse<any>> {
    return this.request('/health');
  }

  async getServiceStatus(): Promise<ApiResponse<any>> {
    return this.request('/health/services');
  }

  // Web Scraping APIs
  async startWebScraping(config: {
    urls: string[];
    domain: string;
    max_depth?: number;
    max_pages?: number;
    delay?: number;
  }): Promise<ApiResponse<{ crawl_id: string; status: string; urls_queued: number; estimated_completion: string }>> {
    return this.request('/web-scraping/start', {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getCrawlStatus(crawlId: string): Promise<ApiResponse<{
    crawl_id: string;
    status: string;
    pages_crawled: number;
    total_pages: number;
    progress_percentage: number;
    started_at?: string;
    completed_at?: string;
    error_message?: string;
  }>> {
    return this.request(`/web-scraping/${crawlId}/status`);
  }

  // Enhanced Web Scraper APIs
  async previewWebScraper(domainId: string, connectorId: string): Promise<ApiResponse<{
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
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/preview`, {
      method: 'POST',
    });
  }

  async testWebScraperConfig(domainId: string, connectorId: string, config: any): Promise<ApiResponse<{
    success: boolean;
    result: any;
    configuration_valid: boolean;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/test-config`, {
      method: 'POST',
      body: JSON.stringify(config),
    });
  }

  async getWebScraperStats(domainId: string, connectorId: string): Promise<ApiResponse<{
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
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/crawl-stats`);
  }

  async getSyncJobs(domainId: string, connectorId: string, params?: {
    skip?: number;
    limit?: number;
    status?: string;
  }): Promise<ApiResponse<Array<{
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
  }>>> {
    const searchParams = new URLSearchParams();
    if (params?.skip) searchParams.append('skip', params.skip.toString());
    if (params?.limit) searchParams.append('limit', params.limit.toString());
    if (params?.status) searchParams.append('status', params.status);

    const queryString = searchParams.toString();
    const url = `/domains/${domainId}/connectors/${connectorId}/sync-jobs${queryString ? `?${queryString}` : ''}`;
    
    return this.request(url);
  }

  async updateCrawlRules(domainId: string, connectorId: string, rules: {
    include_patterns?: string[];
    exclude_patterns?: string[];
    follow_external?: boolean;
    respect_robots?: boolean;
    max_file_size?: number;
    custom_user_agent?: string;
    crawl_frequency_hours?: number;
    content_filters?: {
      min_word_count?: number;
      exclude_nav_elements?: boolean;
      exclude_footer_elements?: boolean;
      extract_metadata?: boolean;
    };
  }): Promise<ApiResponse<{
    success: boolean;
    message: string;
    updated_rules: {
      include_patterns: string[];
      exclude_patterns: string[];
      follow_external: boolean;
      respect_robots: boolean;
      max_file_size: number;
      custom_user_agent: string;
      crawl_frequency_hours: number;
    };
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/crawl-rules`, {
      method: 'PUT',
      body: JSON.stringify(rules),
    });
  }

  async getCrawledPages(domainId: string, connectorId: string, params?: {
    page?: number;
    page_size?: number;
    status_filter?: 'success' | 'failed' | 'skipped';
    search_query?: string;
  }): Promise<ApiResponse<{
    pages: Array<{
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
    }>;
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
  }>> {
    const searchParams = new URLSearchParams();
    if (params?.page) searchParams.append('page', params.page.toString());
    if (params?.page_size) searchParams.append('page_size', params.page_size.toString());
    if (params?.status_filter) searchParams.append('status_filter', params.status_filter);
    if (params?.search_query) searchParams.append('search_query', params.search_query);

    const queryString = searchParams.toString();
    const url = `/domains/${domainId}/connectors/${connectorId}/crawled-pages${queryString ? `?${queryString}` : ''}`;
    
    return this.request(url);
  }

  async deleteCrawledPage(domainId: string, connectorId: string, pageId: string): Promise<ApiResponse<{
    success: boolean;
    message: string;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/crawled-pages/${pageId}`, {
      method: 'DELETE',
    });
  }

  async validateCrawlPatterns(patterns: string[]): Promise<ApiResponse<{
    valid_patterns: string[];
    invalid_patterns: Array<{
      pattern: string;
      error: string;
    }>;
  }>> {
    return this.request('/utils/validate-regex-patterns', {
      method: 'POST',
      body: JSON.stringify({ patterns }),
    });
  }

  async getCrawlInsights(domainId: string, connectorId: string): Promise<ApiResponse<{
    content_quality_distribution: {
      high_quality: number;
      medium_quality: number;
      low_quality: number;
    };
    crawl_efficiency: {
      success_rate: number;
      avg_crawl_time: number;
      pages_per_hour: number;
    };
    content_analysis: {
      avg_word_count: number;
      most_common_content_types: Array<{
        type: string;
        count: number;
      }>;
      language_distribution: Array<{
        language: string;
        count: number;
      }>;
    };
    url_patterns: {
      most_crawled_paths: Array<{
        path_pattern: string;
        count: number;
      }>;
      blocked_patterns: Array<{
        pattern: string;
        blocked_count: number;
      }>;
    };
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/crawl-insights`);
  }

  // Advanced Web Scraper Methods
  async scheduleWebScraperCrawl(domainId: string, connectorId: string): Promise<ApiResponse<{
    status: string;
    message?: string;
    next_run?: string;
    time_until_next_seconds?: number;
    pages_crawled?: number;
    active_crawls?: number;
    error?: string;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/schedule-crawl`, {
      method: 'POST',
    });
  }

  async getWebScraperPerformanceMetrics(domainId: string, connectorId: string): Promise<ApiResponse<{
    metrics: {
      pages_per_second: number;
      avg_response_time: number;
      error_rate: number;
      bandwidth_usage_mb: number;
      cache_hit_rate: number;
      robots_compliance_rate: number;
    };
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/performance-metrics`);
  }

  async getWebScraperOptimizationSuggestions(domainId: string, connectorId: string): Promise<ApiResponse<{
    current_metrics: {
      pages_per_second: number;
      avg_response_time: number;
      error_rate: number;
      bandwidth_usage_mb: number;
      cache_hit_rate: number;
      robots_compliance_rate: number;
    };
    suggestions: Array<{
      type: string;
      severity: 'low' | 'medium' | 'high';
      message: string;
      recommended_action: string;
    }>;
    recommended_settings: Record<string, any>;
    optimization_score: number;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/optimization-suggestions`);
  }

  async applyWebScraperOptimization(
    domainId: string, 
    connectorId: string, 
    optimizationData: { recommended_settings: Record<string, any> }
  ): Promise<ApiResponse<{
    applied_settings: Record<string, any>;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/apply-optimization`, {
      method: 'POST',
      body: JSON.stringify(optimizationData),
    });
  }

  // Organization Member Management APIs
  async getOrganizationMembers(organizationId: string): Promise<ApiResponse<any[]>> {
    return this.request(`/organizations/${organizationId}/members`);
  }

  async inviteOrganizationMember(organizationId: string, data: {
    email: string;
    role: string;
  }): Promise<ApiResponse<any>> {
    return this.request(`/organizations/${organizationId}/members/invite`, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateOrganizationMember(organizationId: string, memberId: string, role: string): Promise<ApiResponse<any>> {
    return this.request(`/organizations/${organizationId}/members/${memberId}?role=${role}`, {
      method: 'PUT',
    });
  }

  async removeOrganizationMember(organizationId: string, memberId: string): Promise<ApiResponse<void>> {
    return this.request(`/organizations/${organizationId}/members/${memberId}`, {
      method: 'DELETE',
    });
  }

  // User Profile Management APIs
  async updateUserProfile(data: {
    full_name?: string;
    email?: string;
    preferences?: any;
  }): Promise<ApiResponse<User>> {
    return this.request('/users/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async changePassword(data: {
    current_password: string;
    new_password: string;
  }): Promise<ApiResponse<{ message: string }>> {
    return this.request('/users/me/password', {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async getUserPreferences(): Promise<ApiResponse<any>> {
    return this.request('/users/me/preferences');
  }

  async updateUserPreferences(preferences: any): Promise<ApiResponse<any>> {
    return this.request('/users/me/preferences', {
      method: 'PUT',
      body: JSON.stringify(preferences),
    });
  }

  // Enhanced Web Scraper APIs (new methods)
  async getWebScraperContentAnalytics(domainId: string, connectorId: string): Promise<ApiResponse<{
    analytics: {
      content_quality_distribution: {
        high_quality: number;
        medium_quality: number;
        low_quality: number;
      };
      duplicate_analysis: {
        unique_content: number;
        near_duplicates: number;
        exact_duplicates: number;
      };
      information_density_stats: {
        avg_density: number;
        high_density_pages: number;
        low_density_pages: number;
      };
      language_distribution: Record<string, number>;
      content_structure_patterns: {
        well_structured: number;
        basic_structure: number;
        poor_structure: number;
      };
      average_quality_score?: number;
    };
    generated_at: string;
    connector_id: string;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/content-analytics`);
  }

  async getCrawlSessionStatus(domainId: string, connectorId: string): Promise<ApiResponse<{
    session?: {
      session_id: string;
      start_time: string;
      duration_seconds: number;
      pages_discovered: number;
      pages_processed: number;
      pages_successful: number;
      pages_failed: number;
      success_rate: number;
      bytes_downloaded: number;
      avg_response_time: number;
      current_queue_size: number;
      estimated_completion?: string;
      pages_per_minute: number;
    };
    status: 'active' | 'inactive';
    message?: string;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/crawl-session-status`);
  }

  async startIntelligentCrawl(domainId: string, connectorId: string, options?: {
    intelligent_discovery?: boolean;
    real_time_monitoring?: boolean;
    quality_threshold?: number;
    duplicate_threshold?: number;
    max_depth?: number;
    max_pages?: number;
  }): Promise<ApiResponse<{
    status: string;
    message: string;
    connector_id: string;
    features_enabled: {
      intelligent_discovery: boolean;
      real_time_monitoring: boolean;
      quality_filtering: boolean;
      duplicate_detection: boolean;
    };
    estimated_start_time: string;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/intelligent-crawl`, {
      method: 'POST',
      body: JSON.stringify(options || {}),
    });
  }

  async getContentQualityReport(domainId: string, connectorId: string): Promise<ApiResponse<{
    report: {
      total_pages: number;
      average_quality_score: number;
      quality_distribution: {
        excellent: number;
        good: number;
        fair: number;
        poor: number;
      };
      recommendations: Array<{
        type: string;
        message: string;
        action: string;
      }>;
      analysis_date: string;
    };
    top_pages: Array<{
      url: string;
      title: string;
      quality_score: number;
      word_count: number;
      last_crawled?: string;
      detailed_metrics?: {
        readability_score: number;
        content_density: number;
        semantic_richness: number;
        information_density: number;
      };
    }>;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/content-quality-report`);
  }

  async updateEnhancedWebScraperConfig(
    domainId: string, 
    connectorId: string, 
    config: {
      intelligent_discovery?: boolean;
      real_time_monitoring?: boolean;
      adaptive_scheduling?: boolean;
      quality_threshold?: number;
      duplicate_threshold?: number;
      max_file_size?: number;
      content_filters?: {
        min_word_count?: number;
        exclude_nav_elements?: boolean;
        exclude_footer_elements?: boolean;
        extract_metadata?: boolean;
      };
      crawl_frequency_hours?: number;
      custom_user_agent?: string;
    }
  ): Promise<ApiResponse<{
    status: string;
    message: string;
    updated_config: Record<string, any>;
    features_enabled: {
      intelligent_discovery: boolean;
      real_time_monitoring: boolean;
      adaptive_scheduling: boolean;
      quality_filtering: boolean;
      duplicate_detection: boolean;
    };
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/enhanced-config`, {
      method: 'PUT',
      body: JSON.stringify(config),
    });
  }

  async getDuplicateContentAnalysis(
    domainId: string, 
    connectorId: string, 
    threshold: number = 0.8
  ): Promise<ApiResponse<{
    analysis: {
      total_pages: number;
      unique_pages: number;
      exact_duplicates: number;
      duplicate_groups: Array<{
        content_hash: string;
        duplicate_count: number;
        pages: Array<{
          id: string;
          url: string;
          title: string;
          word_count: number;
          last_crawled?: string;
        }>;
        similarity_type: string;
      }>;
      duplication_rate: number;
      threshold_used: number;
      analysis_date: string;
    };
    recommendations: Array<{
      type: string;
      message: string;
      action: string;
    }>;
  }>> {
    return this.request(`/domains/${domainId}/connectors/${connectorId}/duplicate-analysis?threshold=${threshold}`);
  }
}

// Create singleton instance
export const api = new ApiClient();

// WebSocket utilities for real-time chat
export class ChatWebSocket {
  private ws: WebSocket | null = null;
  private sessionId: string;
  private onMessage: (message: Message) => void;
  private onError: (error: Event) => void;

  constructor(
    sessionId: string, 
    onMessage: (message: Message) => void,
    onError: (error: Event) => void = () => {}
  ) {
    this.sessionId = sessionId;
    this.onMessage = onMessage;
    this.onError = onError;
  }

  connect() {
    const wsUrl = `ws://localhost:8001/ws/${this.sessionId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      // WebSocket connection established
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (error) {
        // Handle parsing errors silently or with proper error reporting
        this.onError(error as Event);
      }
    };

    this.ws.onerror = (error) => {
      this.onError(error);
    };

    this.ws.onclose = () => {
      // WebSocket connection closed
    };
  }

  sendMessage(message: string) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify({ message }));
    }
  }

  disconnect() {
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
  }
}

export default api; 