import React, { useState } from 'react';
import { X, ExternalLink, FileText, Book } from 'lucide-react';

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

  // Extract clean document title (remove chunk part numbers)
  const getCleanTitle = (title: string) => {
    // Remove patterns like "(Part 123)" or "- Part 123" from the title
    return title.replace(/\s*[-–]\s*Part\s+\d+|\s*\(Part\s+\d+\)/gi, '').trim();
  };

  // Determine document type
  const getDocumentType = (title: string, domain: string) => {
    if (title.toLowerCase().includes('report') || title.toLowerCase().includes('pdf')) {
      return { icon: FileText, label: 'Document' };
    }
    if (domain.toLowerCase().includes('help') || domain.toLowerCase().includes('support')) {
      return { icon: Book, label: 'Help Article' };
    }
    return { icon: FileText, label: 'Document' };
  };

  const loadFullDocument = async () => {
    setLoadingFullContent(true);
    try {
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

  const cleanTitle = getCleanTitle(source.title);
  const docType = getDocumentType(source.title, source.domain);
  const DocIcon = docType.icon;

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-lg max-w-4xl w-full max-h-[85vh] overflow-hidden shadow-xl">
        <div className="flex items-center justify-between p-6 border-b border-gray-200">
          <div className="flex items-center space-x-3">
            <div className="p-2 bg-blue-50 rounded-lg">
              <DocIcon className="h-6 w-6 text-blue-600" />
            </div>
            <div>
              <h3 className="text-xl font-semibold text-gray-900">{cleanTitle}</h3>
              <div className="flex items-center space-x-4 text-sm text-gray-500 mt-1">
                <span className="flex items-center space-x-1">
                  <span className="w-2 h-2 bg-green-500 rounded-full"></span>
                  <span>{source.confidence_score} confidence</span>
                </span>
                <span>•</span>
                <span>{docType.label}</span>
                <span>•</span>
                <span>{source.domain} domain</span>
              </div>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        
        <div className="p-6 overflow-y-auto max-h-[70vh]">
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-gray-900 mb-3 flex items-center space-x-2">
                <Book className="h-4 w-4" />
                <span>Relevant Content</span>
              </h4>
              <div className="bg-gray-50 border border-gray-200 rounded-lg p-4">
                <p className="text-gray-700 leading-relaxed">
                  {source.excerpt || source.preview}
                </p>
              </div>
            </div>
            
            {source.full_content && (
              <div>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="font-semibold text-gray-900 flex items-center space-x-2">
                    <FileText className="h-4 w-4" />
                    <span>Full Context</span>
                  </h4>
                  <button
                    onClick={loadFullDocument}
                    disabled={loadingFullContent}
                    className="text-sm text-blue-600 hover:text-blue-800 font-medium px-3 py-1 rounded-md hover:bg-blue-50 transition-colors"
                  >
                    {loadingFullContent ? 'Loading...' : 'View Complete Document'}
                  </button>
                </div>
                
                <div className="bg-white border border-gray-200 rounded-lg p-4 max-h-96 overflow-y-auto">
                  <div className="text-sm text-gray-700 leading-relaxed">
                    {fullDocumentContent ? (
                      <pre className="whitespace-pre-wrap font-sans">
                        {fullDocumentContent}
                      </pre>
                    ) : (
                      <pre className="whitespace-pre-wrap font-sans">
                        {source.full_content}
                      </pre>
                    )}
                  </div>
                </div>
              </div>
            )}
            
            <div className="flex items-center justify-between pt-4 border-t border-gray-200">
              <div className="text-sm text-gray-500">
                <span>Source: {cleanTitle}</span>
                {source.word_count && <span> • {source.word_count} words</span>}
              </div>
              <div className="flex items-center space-x-3">
                {source.url && (
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center space-x-2 text-blue-600 hover:text-blue-800 text-sm font-medium px-3 py-1 rounded-md hover:bg-blue-50 transition-colors"
                  >
                    <ExternalLink className="h-4 w-4" />
                    <span>Open Original</span>
                  </a>
                )}
                <button
                  onClick={onClose}
                  className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 hover:bg-gray-100 rounded-md transition-colors"
                >
                  Close
                </button>
              </div>
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

  // Helper function to get clean title
  const getCleanTitle = (title: string) => {
    return title.replace(/\s*[-–]\s*Part\s+\d+|\s*\(Part\s+\d+\)/gi, '').trim();
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
            const cleanTitle = source ? getCleanTitle(source.title) : 'Unknown Source';
            const preview = source ? (source.excerpt || source.preview) : 'No preview available';
            
            return (
              <button
                key={index}
                onClick={() => handleCitationClick(part)}
                className="group relative inline-flex items-center mx-0.5 px-1.5 py-0.5 text-xs font-semibold text-blue-700 bg-blue-100 hover:bg-blue-200 rounded-md transition-all duration-200 border border-blue-200 hover:border-blue-300 cursor-pointer hover:scale-105"
                title={`Click to view: ${cleanTitle}`}
              >
                <span className="relative z-10">[{part.number}]</span>
                
                {/* Hover tooltip */}
                <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded-lg shadow-lg opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none z-50 max-w-xs">
                  <div className="font-medium mb-1">{cleanTitle}</div>
                  <div className="text-gray-300 line-clamp-3">{preview.slice(0, 120)}...</div>
                  {source && (
                    <div className="text-gray-400 mt-1 text-xs">{source.confidence_score} confidence</div>
                  )}
                  {/* Arrow */}
                  <div className="absolute top-full left-1/2 transform -translate-x-1/2 w-0 h-0 border-l-4 border-r-4 border-t-4 border-transparent border-t-gray-900"></div>
                </div>
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