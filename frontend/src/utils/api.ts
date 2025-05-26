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
      this.token = localStorage.getItem('rag_token');
    }
  }

  setToken(token: string) {
    this.token = token;
    if (typeof window !== 'undefined') {
      localStorage.setItem('rag_token', token);
    }
  }

  clearToken() {
    this.token = null;
    if (typeof window !== 'undefined') {
      localStorage.removeItem('rag_token');
    }
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
}

// Create singleton instance
export const apiClient = new ApiClient();

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

export default apiClient; 