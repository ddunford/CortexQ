import React, { useState } from 'react';
import { X, ExternalLink } from 'lucide-react';

interface Citation {
  citationId: string;
  sourceIndex: number;
  number: string;
}

interface Source {
  id: string;
  title: string;
  preview: string;
  excerpt: string;
  full_content?: string;
  url?: string;
  domain: string;
  similarity: number;
  confidence_score: string;
  chunk_index: number;
  content_length: number;
  word_count: number;
  citation_id: string;
}

interface CitationTextProps {
  content: string;
  sources?: Source[];
  className?: string;
}

interface SourceModalProps {
  source: Source;
  isOpen: boolean;
  onClose: () => void;
}

const SourceModal: React.FC<SourceModalProps> = ({ source, isOpen, onClose }) => {
  const [fullDocumentContent, setFullDocumentContent] = useState<string | null>(null);
  const [loadingFullContent, setLoadingFullContent] = useState(false);

  if (!isOpen) return null;

  // Check if content appears truncated
  const contentAppearsTruncated = source.full_content && (
    source.full_content.endsWith('...') || 
    source.full_content.length < source.content_length * 0.8 ||
    !source.full_content.trim().endsWith('.') && !source.full_content.trim().endsWith('!') && !source.full_content.trim().endsWith('?')
  );

  const loadFullDocument = async () => {
    setLoadingFullContent(true);
    try {
      // Call the source content API to get the complete content
      const response = await fetch(`http://localhost:8001/sources/${source.id}/content?chunk_index=${source.chunk_index}`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
      });
      
      if (response.ok) {
        const data = await response.json();
        setFullDocumentContent(data.content || data.full_content);
      }
    } catch (error) {
      console.error('Failed to load full document content:', error);
    } finally {
      setLoadingFullContent(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[85vh] overflow-hidden">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">{source.title}</h3>
            <p className="text-sm text-gray-500">
              Confidence: {source.confidence_score} • {source.word_count} words • Chunk {source.chunk_index + 1}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="p-4 overflow-y-auto max-h-[70vh]">
          <div className="space-y-4">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">Preview</h4>
              <p className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg">
                {source.excerpt || source.preview}
              </p>
            </div>
            
            {source.full_content && (
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-medium text-gray-900">Content (This Chunk)</h4>
                  {contentAppearsTruncated && (
                    <button
                      onClick={loadFullDocument}
                      disabled={loadingFullContent}
                      className="text-sm text-blue-600 hover:text-blue-800 font-medium"
                    >
                      {loadingFullContent ? 'Loading...' : 'Load Full Document'}
                    </button>
                  )}
                </div>
                
                {contentAppearsTruncated && (
                  <div className="mb-2 p-2 bg-yellow-50 border border-yellow-200 rounded text-sm text-yellow-800">
                    ⚠️ This content appears to be truncated. Click "Load Full Document" to see the complete text.
                  </div>
                )}
                
                <div className="text-sm text-gray-700 bg-gray-50 p-3 rounded-lg max-h-96 overflow-y-auto">
                  <pre className="whitespace-pre-wrap font-sans">
                    {fullDocumentContent || source.full_content}
                  </pre>
                </div>
              </div>
            )}
            
            <div className="flex items-center justify-between pt-2 border-t border-gray-200">
              <div className="text-xs text-gray-500">
                Domain: {source.domain} • Chunk: {source.chunk_index + 1} • Length: {source.content_length} chars
              </div>
              {source.url && (
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center space-x-1 text-blue-600 hover:text-blue-800 text-sm"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span>Open Source</span>
                </a>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const CitationText: React.FC<CitationTextProps> = ({ content, sources = [], className = '' }) => {
  const [selectedSource, setSelectedSource] = useState<Source | null>(null);

  const parseCitations = (htmlContent: string): (string | Citation)[] => {
    const parts: (string | Citation)[] = [];
    const citeRegex = /<cite\s+data-citation-id="([^"]+)"\s+data-source-index="([^"]+)">(\[(\d+)\])<\/cite>/g;
    
    let lastIndex = 0;
    let match;
    
    while ((match = citeRegex.exec(htmlContent)) !== null) {
      // Add text before citation
      if (match.index > lastIndex) {
        parts.push(htmlContent.slice(lastIndex, match.index));
      }
      
      // Add citation object
      parts.push({
        citationId: match[1],
        sourceIndex: parseInt(match[2]),
        number: match[4]
      });
      
      lastIndex = match.index + match[0].length;
    }
    
    // Add remaining text
    if (lastIndex < htmlContent.length) {
      parts.push(htmlContent.slice(lastIndex));
    }
    
    return parts;
  };

  const handleCitationClick = (citation: Citation) => {
    const source = sources[citation.sourceIndex];
    if (source) {
      setSelectedSource(source);
    }
  };

  const parts = parseCitations(content);

  return (
    <>
      <span className={className}>
        {parts.map((part, index) => {
          if (typeof part === 'string') {
            return <span key={index}>{part}</span>;
          } else {
            // It's a citation
            const source = sources[part.sourceIndex];
            return (
              <button
                key={index}
                onClick={() => handleCitationClick(part)}
                className="inline-flex items-center text-blue-600 hover:text-blue-800 hover:bg-blue-50 rounded px-1 transition-colors cursor-pointer font-medium"
                title={source ? `Click to view: ${source.title}` : 'View source'}
              >
                [{part.number}]
              </button>
            );
          }
        })}
      </span>
      
      {selectedSource && (
        <SourceModal
          source={selectedSource}
          isOpen={!!selectedSource}
          onClose={() => setSelectedSource(null)}
        />
      )}
    </>
  );
};

export default CitationText; 