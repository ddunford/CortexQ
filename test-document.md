# Enterprise RAG System Documentation

## Overview
This is a test document for the Enterprise RAG (Retrieval-Augmented Generation) system. The system allows users to upload documents and chat with their knowledge base using natural language queries.

## Key Features

### File Upload and Processing
- Support for multiple file formats: PDF, DOCX, TXT, MD, JSON, CSV, and code files
- Automatic text extraction and chunking
- Vector embedding generation using Ollama or OpenAI
- Multi-domain organization (general, support, sales, engineering, product)

### Chat Interface
- Real-time WebSocket communication
- Session management with conversation history
- Domain-specific search and responses
- Source attribution for answers

### Search Capabilities
- Vector similarity search using embeddings
- Hybrid search combining vector and keyword matching
- Cross-domain search functionality
- Confidence scoring for results

## Technical Architecture

### Services
1. **File Service** (Port 8001) - Handles file uploads and processing
2. **Vector Service** (Port 8002) - Manages embeddings and vector search
3. **Chat API** (Port 8003) - Provides chat interface and WebSocket support
4. **Web UI** (Port 8080) - User-friendly web interface

### Database
- PostgreSQL with pgvector extension for vector storage
- Redis for caching and session management

## Usage Examples

### Uploading Documents
1. Select a domain (general, support, sales, engineering, product)
2. Click the file upload area
3. Choose one or more files
4. Files are automatically processed and indexed

### Chatting with Documents
1. Type a question in the chat input
2. The system searches relevant documents
3. Generates a response based on found content
4. Shows source documents for transparency

## Sample Questions to Try
- "What are the key features of this system?"
- "How does the file upload process work?"
- "What ports do the services run on?"
- "Explain the technical architecture"

## Troubleshooting

### Service Health Checks
- File Service: http://localhost:8001/health
- Vector Service: http://localhost:8002/health  
- Chat API: http://localhost:8003/health
- Web UI: http://localhost:8080/health

### Common Issues
- **Upload fails**: Check file format is supported
- **Chat not responding**: Verify WebSocket connection
- **No search results**: Ensure documents are processed and indexed

## Development Notes
This is an MVP (Minimum Viable Product) demonstrating core RAG functionality. Future enhancements may include:
- Real LLM integration (currently using mock embeddings)
- Advanced document parsing
- User authentication and authorization
- Analytics and monitoring dashboards 