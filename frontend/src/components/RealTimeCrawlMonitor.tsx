import React, { useState, useEffect, useRef } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from './ui/card';
import { Badge } from './ui/badge';
import { Progress } from './ui/progress';

interface CrawlProgress {
  type: string;
  total_pages?: number;
  new_pages?: number;
  recent_activity?: number;
  last_activity?: string;
  recent_pages?: Array<{
    url: string;
    title: string;
    status: string;
    crawled_at: string;
  }>;
  timestamp: string;
}

interface SyncStatus {
  type: string;
  sync_job_id: string;
  status: string;
  started_at?: string;
  metadata?: any;
  timestamp: string;
}

interface RealTimeCrawlMonitorProps {
  connectorId: string;
  domainId: string;
  isActive: boolean;
}

export function RealTimeCrawlMonitor({ connectorId, domainId, isActive }: RealTimeCrawlMonitorProps) {
  const [connected, setConnected] = useState(false);
  const [crawlProgress, setCrawlProgress] = useState<CrawlProgress | null>(null);
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [totalPages, setTotalPages] = useState(0);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!isActive || !connectorId || !domainId) {
      return;
    }

    // Get JWT token from localStorage (adjust based on your auth implementation)
    const token = localStorage.getItem('token') || 'dummy-token';
    
    // Connect to WebSocket
    const wsUrl = `ws://localhost:8001/api/domains/${domainId}/connectors/${connectorId}/crawl-progress?token=${token}`;
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('Connected to crawl progress WebSocket');
        setConnected(true);
        setConnectionError(null);
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          console.log('WebSocket message:', data);

          switch (data.type) {
            case 'connected':
              console.log('WebSocket connection confirmed:', data.message);
              break;
            
            case 'crawl_progress':
              setCrawlProgress(data);
              if (data.total_pages !== undefined) {
                setTotalPages(data.total_pages);
              }
              break;
            
            case 'sync_status':
              setSyncStatus(data);
              break;
            
            case 'error':
              console.error('WebSocket error:', data.message);
              setConnectionError(data.message);
              break;
            
            default:
              console.log('Unknown message type:', data.type);
          }
        } catch (error) {
          console.error('Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('WebSocket connection error');
        setConnected(false);
      };

      ws.onclose = () => {
        console.log('WebSocket connection closed');
        setConnected(false);
      };

      return () => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.close();
        }
      };
    } catch (error) {
      console.error('Error creating WebSocket connection:', error);
      setConnectionError('Failed to create WebSocket connection');
    }
  }, [connectorId, domainId, isActive]);

  if (!isActive) {
    return (
      <Card className="w-full">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            📡 Real-Time Crawl Monitor
            <Badge variant="secondary">Inactive</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-gray-500">Monitor will activate when crawling starts</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          📡 Real-Time Crawl Monitor
          <Badge variant={connected ? "default" : "destructive"}>
            {connected ? "Connected" : "Disconnected"}
          </Badge>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {connectionError && (
          <div className="bg-red-50 border border-red-200 rounded-md p-3">
            <p className="text-red-800 text-sm">Error: {connectionError}</p>
          </div>
        )}

        {/* Sync Job Status */}
        {syncStatus && (
          <div className="bg-blue-50 border border-blue-200 rounded-md p-3">
            <h4 className="font-medium text-blue-900 mb-2">Sync Job Status</h4>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="font-medium">Job ID:</span> {syncStatus.sync_job_id.slice(0, 8)}...
              </div>
              <div>
                <span className="font-medium">Status:</span> 
                <Badge variant={syncStatus.status === 'running' ? 'default' : 'secondary'} className="ml-1">
                  {syncStatus.status}
                </Badge>
              </div>
              {syncStatus.started_at && (
                <div className="col-span-2">
                  <span className="font-medium">Started:</span> {new Date(syncStatus.started_at).toLocaleTimeString()}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Crawl Progress */}
        {crawlProgress && (
          <div className="space-y-3">
            <div>
              <div className="flex justify-between items-center mb-2">
                <h4 className="font-medium">Crawl Progress</h4>
                <span className="text-sm text-gray-500">
                  {totalPages} pages total
                </span>
              </div>
              
              {crawlProgress.new_pages !== undefined && crawlProgress.new_pages > 0 && (
                <div className="bg-green-50 border border-green-200 rounded-md p-2 mb-2">
                  <p className="text-green-800 text-sm">
                    🆕 {crawlProgress.new_pages} new pages crawled
                  </p>
                </div>
              )}

              {crawlProgress.recent_activity !== undefined && crawlProgress.recent_activity > 0 && (
                <div className="bg-blue-50 border border-blue-200 rounded-md p-2 mb-2">
                  <p className="text-blue-800 text-sm">
                    ⚡ {crawlProgress.recent_activity} pages crawled in the last minute
                  </p>
                </div>
              )}
            </div>

            {/* Recent Pages */}
            {crawlProgress.recent_pages && crawlProgress.recent_pages.length > 0 && (
              <div>
                <h5 className="font-medium mb-2">Recently Crawled Pages</h5>
                <div className="space-y-2 max-h-40 overflow-y-auto">
                  {crawlProgress.recent_pages.map((page, index) => (
                    <div key={index} className="bg-gray-50 border border-gray-200 rounded-md p-2">
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate" title={page.title}>
                            {page.title || 'Untitled'}
                          </p>
                          <p className="text-xs text-gray-500 truncate" title={page.url}>
                            {page.url}
                          </p>
                        </div>
                        <div className="flex items-center gap-2">
                          <Badge 
                            variant={page.status === 'success' ? 'default' : 'destructive'}
                            className="text-xs"
                          >
                            {page.status}
                          </Badge>
                          <span className="text-xs text-gray-400">
                            {new Date(page.crawled_at).toLocaleTimeString()}
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Last Activity */}
            {crawlProgress.last_activity && (
              <div className="text-xs text-gray-500">
                Last activity: {new Date(crawlProgress.last_activity).toLocaleString()}
              </div>
            )}
          </div>
        )}

        {/* No Activity Message */}
        {connected && !crawlProgress && !syncStatus && (
          <div className="text-center py-6">
            <div className="animate-pulse">
              <div className="w-8 h-8 bg-blue-200 rounded-full mx-auto mb-2"></div>
              <p className="text-gray-500 text-sm">Waiting for crawl activity...</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
} 