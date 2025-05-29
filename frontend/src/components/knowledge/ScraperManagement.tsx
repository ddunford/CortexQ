import React, { useState, useEffect } from 'react';
import {
  Globe,
  Search,
  Eye,
  Edit,
  RefreshCw,
  Ban,
  Check,
  Trash2,
  Filter,
  ChevronLeft,
  ChevronRight,
  Calendar,
  FileText,
  Image,
  Link as LinkIcon,
  AlertCircle,
  CheckCircle
} from 'lucide-react';
import Button from '../ui/Button';
import Input from '../ui/Input';
import Card from '../ui/Card';
import { api } from '../../utils/api';

interface ScrapedPage {
  id: string;
  url: string;
  title: string;
  status: string;
  content_type: string;
  word_count: number;
  first_crawled: string;
  last_crawled: string;
  depth: number;
  blocked: boolean;
  block_reason?: string;
  domain: string;
  connector_name: string;
  embedding_count: number;
  image_embedding_count: number;
  has_images: boolean;
  image_count: number;
}

interface ScrapedPageDetails extends ScrapedPage {
  content: string;
  metadata: any;
  visual_content: any;
  embeddings: Array<{
    id: string;
    content_preview: string;
    model: string;
    created_at: string;
  }>;
  image_embeddings: Array<{
    id: string;
    description: string;
    model: string;
    created_at: string;
  }>;
}

interface PaginationInfo {
  page: number;
  limit: number;
  total: number;
  pages: number;
}

export default function ScraperManagement() {
  const [pages, setPages] = useState<ScrapedPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedPage, setSelectedPage] = useState<ScrapedPageDetails | null>(null);
  const [showModal, setShowModal] = useState(false);
  const [modalMode, setModalMode] = useState<'view' | 'edit'>('view');
  const [editForm, setEditForm] = useState({ title: '', content: '' });
  const [pagination, setPagination] = useState<PaginationInfo>({
    page: 1,
    limit: 20,
    total: 0,
    pages: 0
  });
  
  // Filters
  const [filters, setFilters] = useState({
    search: '',
    domain: '',
    status: '',
    blockedOnly: false
  });

  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    loadPages();
  }, [pagination.page, filters]);

  const loadPages = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: pagination.page.toString(),
        limit: pagination.limit.toString()
      });

      if (filters.search) params.append('search', filters.search);
      if (filters.domain) params.append('domain', filters.domain);
      if (filters.status) params.append('status', filters.status);
      if (filters.blockedOnly) params.append('blocked_only', 'true');

      const response = await fetch(`http://localhost:8001/api/scraper/pages?${params}`, {
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const data = await response.json();
        setPages(data.pages);
        setPagination(data.pagination);
      } else {
        showMessage('Failed to load pages', 'error');
      }
    } catch (error) {
      showMessage('Error loading pages', 'error');
    } finally {
      setLoading(false);
    }
  };

  const loadPageDetails = async (pageId: string) => {
    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${pageId}`, {
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        const pageDetails = await response.json();
        setSelectedPage(pageDetails);
        setEditForm({
          title: pageDetails.title || '',
          content: pageDetails.content || ''
        });
      } else {
        showMessage('Failed to load page details', 'error');
      }
    } catch (error) {
      showMessage('Error loading page details', 'error');
    }
  };

  const handleView = async (page: ScrapedPage) => {
    await loadPageDetails(page.id);
    setModalMode('view');
    setShowModal(true);
  };

  const handleEdit = async (page: ScrapedPage) => {
    await loadPageDetails(page.id);
    setModalMode('edit');
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!selectedPage) return;

    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${selectedPage.id}`, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(editForm)
      });

      if (response.ok) {
        showMessage('Page updated successfully!', 'success');
        setShowModal(false);
        loadPages();
      } else {
        showMessage('Failed to update page', 'error');
      }
    } catch (error) {
      showMessage('Error updating page', 'error');
    }
  };

  const handleRescrape = async (pageId: string) => {
    if (!confirm('Re-scrape this page? This will update the content and images.')) return;

    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${pageId}/rescrape`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        }
      });

      const result = await response.json();
      if (result.success) {
        showMessage('Page re-scraped successfully!', 'success');
        loadPages();
      } else {
        showMessage(`Re-scrape failed: ${result.message}`, 'error');
      }
    } catch (error) {
      showMessage('Error re-scraping page', 'error');
    }
  };

  const handleBlock = async (pageId: string) => {
    const reason = prompt('Reason for blocking this page (optional):') || 'Manually blocked';

    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${pageId}/block`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ reason })
      });

      if (response.ok) {
        showMessage('Page blocked successfully!', 'success');
        loadPages();
      } else {
        showMessage('Failed to block page', 'error');
      }
    } catch (error) {
      showMessage('Error blocking page', 'error');
    }
  };

  const handleUnblock = async (pageId: string) => {
    if (!confirm('Unblock this page for future crawling?')) return;

    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${pageId}/unblock`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        showMessage('Page unblocked successfully!', 'success');
        loadPages();
      } else {
        showMessage('Failed to unblock page', 'error');
      }
    } catch (error) {
      showMessage('Error unblocking page', 'error');
    }
  };

  const handleDelete = async (pageId: string) => {
    if (!confirm('Delete this page and all its embeddings? This cannot be undone!')) return;

    try {
      const response = await fetch(`http://localhost:8001/api/scraper/pages/${pageId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${api.getToken()}`,
          'Content-Type': 'application/json'
        }
      });

      if (response.ok) {
        showMessage('Page deleted successfully!', 'success');
        loadPages();
      } else {
        showMessage('Failed to delete page', 'error');
      }
    } catch (error) {
      showMessage('Error deleting page', 'error');
    }
  };

  const showMessage = (text: string, type: 'success' | 'error') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString();
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'success':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <AlertCircle className="h-4 w-4 text-red-500" />;
      default:
        return <Globe className="h-4 w-4 text-gray-500" />;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Scraper Management</h1>
          <p className="text-gray-600">Manage scraped content, review images, and control crawling behavior</p>
        </div>
        <Button onClick={loadPages} className="flex items-center space-x-2">
          <RefreshCw className="h-4 w-4" />
          <span>Refresh</span>
        </Button>
      </div>

      {/* Message */}
      {message && (
        <div className={`p-4 rounded-lg ${message.type === 'success' ? 'bg-green-50 text-green-800 border border-green-200' : 'bg-red-50 text-red-800 border border-red-200'}`}>
          {message.text}
        </div>
      )}

      {/* Filters */}
      <Card className="p-4">
        <div className="flex flex-wrap gap-4 items-center">
          <div className="flex-1 min-w-64">
            <Input
              placeholder="Search pages..."
              value={filters.search}
              onChange={(e) => setFilters(prev => ({ ...prev, search: e.target.value }))}
              className="w-full"
            />
          </div>
          <select
            value={filters.domain}
            onChange={(e) => setFilters(prev => ({ ...prev, domain: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Domains</option>
            <option value="general">General</option>
            <option value="test">Test</option>
          </select>
          <select
            value={filters.status}
            onChange={(e) => setFilters(prev => ({ ...prev, status: e.target.value }))}
            className="px-3 py-2 border border-gray-300 rounded-lg"
          >
            <option value="">All Status</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
          <label className="flex items-center space-x-2">
            <input
              type="checkbox"
              checked={filters.blockedOnly}
              onChange={(e) => setFilters(prev => ({ ...prev, blockedOnly: e.target.checked }))}
            />
            <span>Blocked Only</span>
          </label>
        </div>
      </Card>

      {/* Pages List */}
      <Card>
        {loading ? (
          <div className="p-8 text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cortex-primary mx-auto"></div>
            <p className="mt-2 text-gray-600">Loading pages...</p>
          </div>
        ) : pages.length === 0 ? (
          <div className="p-8 text-center">
            <Globe className="h-12 w-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600">No pages found</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {pages.map((page) => (
              <div
                key={page.id}
                className={`p-4 flex items-center justify-between hover:bg-gray-50 ${page.blocked ? 'bg-red-50 border-l-4 border-red-500' : ''}`}
              >
                <div className="flex-1">
                  <div className="flex items-center space-x-2 mb-2">
                    {getStatusIcon(page.status)}
                    <h3 className="font-medium text-gray-900 truncate">{page.title || 'Untitled'}</h3>
                    {page.blocked && (
                      <span className="px-2 py-1 text-xs bg-red-100 text-red-800 rounded">
                        Blocked
                      </span>
                    )}
                  </div>
                  <p className="text-sm text-gray-600 truncate mb-2">{page.url}</p>
                  <div className="flex items-center space-x-4 text-xs text-gray-500">
                    <span className="flex items-center space-x-1">
                      <FileText className="h-3 w-3" />
                      <span>{page.word_count} words</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <LinkIcon className="h-3 w-3" />
                      <span>{page.embedding_count} embeddings</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <Image className="h-3 w-3" />
                      <span>{page.image_count} images</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <Calendar className="h-3 w-3" />
                      <span>{formatDate(page.last_crawled || page.first_crawled)}</span>
                    </span>
                    {page.blocked && page.block_reason && (
                      <span className="text-red-600">Reason: {page.block_reason}</span>
                    )}
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleView(page)}
                    className="flex items-center space-x-1"
                  >
                    <Eye className="h-4 w-4" />
                    <span>View</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEdit(page)}
                    className="flex items-center space-x-1"
                  >
                    <Edit className="h-4 w-4" />
                    <span>Edit</span>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleRescrape(page.id)}
                    className="flex items-center space-x-1"
                  >
                    <RefreshCw className="h-4 w-4" />
                    <span>Re-scrape</span>
                  </Button>
                  {page.blocked ? (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleUnblock(page.id)}
                      className="flex items-center space-x-1 text-green-600"
                    >
                      <Check className="h-4 w-4" />
                      <span>Unblock</span>
                    </Button>
                  ) : (
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleBlock(page.id)}
                      className="flex items-center space-x-1 text-red-600"
                    >
                      <Ban className="h-4 w-4" />
                      <span>Block</span>
                    </Button>
                  )}
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDelete(page.id)}
                    className="flex items-center space-x-1 text-red-600"
                  >
                    <Trash2 className="h-4 w-4" />
                    <span>Delete</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination */}
        {pagination.pages > 1 && (
          <div className="px-4 py-3 border-t border-gray-200 flex items-center justify-between">
            <div className="text-sm text-gray-600">
              Showing {((pagination.page - 1) * pagination.limit) + 1} to {Math.min(pagination.page * pagination.limit, pagination.total)} of {pagination.total} pages
            </div>
            <div className="flex items-center space-x-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPagination(prev => ({ ...prev, page: prev.page - 1 }))}
                disabled={pagination.page === 1}
                className="flex items-center space-x-1"
              >
                <ChevronLeft className="h-4 w-4" />
                <span>Previous</span>
              </Button>
              <span className="text-sm text-gray-600">
                Page {pagination.page} of {pagination.pages}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setPagination(prev => ({ ...prev, page: prev.page + 1 }))}
                disabled={pagination.page === pagination.pages}
                className="flex items-center space-x-1"
              >
                <span>Next</span>
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {/* Modal */}
      {showModal && selectedPage && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg p-6 max-w-4xl max-h-screen overflow-y-auto w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">
                {modalMode === 'view' ? 'View Page' : 'Edit Page'}
              </h2>
              <Button
                variant="ghost"
                onClick={() => setShowModal(false)}
                className="text-gray-500"
              >
                ×
              </Button>
            </div>

            {modalMode === 'view' ? (
              <div className="space-y-4">
                <div>
                  <h3 className="font-semibold mb-2">📄 {selectedPage.title}</h3>
                  <p className="text-sm text-gray-600 mb-2">
                    <strong>URL:</strong> <a href={selectedPage.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">{selectedPage.url}</a>
                  </p>
                  <p className="text-sm text-gray-600 mb-2"><strong>Status:</strong> {selectedPage.status}</p>
                  <p className="text-sm text-gray-600 mb-2"><strong>Word Count:</strong> {selectedPage.word_count}</p>
                  <p className="text-sm text-gray-600 mb-2"><strong>Domain:</strong> {selectedPage.domain}</p>
                  <p className="text-sm text-gray-600 mb-4"><strong>Last Crawled:</strong> {formatDate(selectedPage.last_crawled)}</p>
                </div>

                <div>
                  <h4 className="font-semibold mb-2">📝 Content Preview</h4>
                  <div className="max-h-48 overflow-y-auto bg-gray-50 p-3 rounded text-sm">
                    {selectedPage.content ? selectedPage.content.substring(0, 1000) + '...' : 'No content'}
                  </div>
                </div>

                {selectedPage.visual_content && (selectedPage.visual_content.screenshots || selectedPage.visual_content.images) && (
                  <div>
                    <h4 className="font-semibold mb-2">📸 Images ({selectedPage.visual_content.screenshots?.length || 0} screenshots, {selectedPage.visual_content.images?.length || 0} images)</h4>
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                      {(selectedPage.visual_content.screenshots || []).map((img: any, index: number) => (
                        <div key={index} className="border rounded overflow-hidden">
                          <img src={img.stored_url} alt={img.alt_text || 'Screenshot'} className="w-full h-32 object-cover" />
                          <div className="p-2 text-xs">
                            <strong>📸 Screenshot</strong><br />
                            {img.enhanced_description || img.alt_text || 'No description'}
                          </div>
                        </div>
                      ))}
                      {(selectedPage.visual_content.images || []).map((img: any, index: number) => (
                        <div key={index} className="border rounded overflow-hidden">
                          <img src={img.stored_url} alt={img.alt_text || 'Image'} className="w-full h-32 object-cover" />
                          <div className="p-2 text-xs">
                            <strong>🖼️ Image</strong><br />
                            {img.enhanced_description || img.alt_text || 'No description'}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div>
                  <h4 className="font-semibold mb-2">🔍 Embeddings</h4>
                  <p className="text-sm text-gray-600">Text Embeddings: {selectedPage.embeddings.length}</p>
                  <p className="text-sm text-gray-600">Image Description Embeddings: {selectedPage.image_embeddings.length}</p>
                </div>
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-2">Title:</label>
                  <Input
                    value={editForm.title}
                    onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))}
                    className="w-full"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-2">Content:</label>
                  <textarea
                    value={editForm.content}
                    onChange={(e) => setEditForm(prev => ({ ...prev, content: e.target.value }))}
                    rows={10}
                    className="w-full p-3 border border-gray-300 rounded-lg"
                  />
                </div>
                <div className="flex justify-end space-x-2">
                  <Button variant="ghost" onClick={() => setShowModal(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleSave}>
                    Save Changes
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
} 