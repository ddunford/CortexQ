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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

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
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }

    try {
      const response = await fetch(url, {
        ...options,
        headers,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      return {
        data,
        success: true,
      };
    } catch (error) {
      console.error('API request failed:', error);
      return {
        data: null as any,
        success: false,
        message: error instanceof Error ? error.message : 'Unknown error',
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
    username: string;
    firstName?: string;
    lastName?: string;
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
    domain?: string;
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
  async uploadFile(file: File, domain: string): Promise<ApiResponse<Document>> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('domain', domain);

    return this.request('/files/upload', {
      method: 'POST',
      headers: {}, // Remove Content-Type to let browser set it for FormData
      body: formData,
    });
  }

  async getFiles(domainId?: string): Promise<ApiResponse<Document[]>> {
    const endpoint = domainId ? `/files?domain_id=${domainId}` : '/files';
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

  // Search APIs
  async search(query: SearchQuery): Promise<ApiResponse<SearchResult[]>> {
    return this.request('/search', {
      method: 'POST',
      body: JSON.stringify(query),
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
      console.log('WebSocket connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.onMessage(data);
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error);
      }
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket error:', error);
      this.onError(error);
    };

    this.ws.onclose = () => {
      console.log('WebSocket disconnected');
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