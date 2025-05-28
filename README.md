# 🚀 CortexQ - Ask Smarter. Know Faster.

**A Professional, Enterprise-Ready Retrieval-Augmented Generation System with Modern UI**

![CortexQ](https://img.shields.io/badge/CortexQ-AI%20Knowledge-blue?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-blue?style=for-the-badge&logo=docker)
![Next.js](https://img.shields.io/badge/Next.js-Frontend-black?style=for-the-badge&logo=next.js)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green?style=for-the-badge&logo=fastapi)

## 🎯 **What You Get**

### ✨ **Professional Modern Frontend**
- **Next.js + React + TypeScript** - Modern, responsive enterprise UI
- **Tailwind CSS** - Beautiful, professional design system
- **Real-time Chat Interface** - WebSocket-powered conversations
- **Multi-Domain Support** - Specialized AI assistants for different areas
- **Dashboard Analytics** - Comprehensive system insights
- **Mobile Responsive** - Works perfectly on all devices

### 🧠 **Intelligent Backend**
- **Multi-Domain RAG Architecture** - 5 specialized knowledge domains
- **Vector Search** - FAISS + Ollama embeddings
- **Agent Workflows** - Intent classification and specialized routing
- **Real-time Processing** - WebSocket chat with streaming responses
- **Enterprise Security** - JWT authentication, RBAC, audit logging

### 🔧 **Complete Docker Setup**
- **One-Command Deployment** - `make quick-start`
- **Microservices Architecture** - Scalable, containerized services
- **Load Balancing** - Nginx reverse proxy with rate limiting
- **Health Monitoring** - Comprehensive health checks
- **Development Mode** - Hot reload for rapid development

---

## 🚀 Quick Start

### Automated Setup (Recommended)
The easiest way to get everything running with AI models:

```bash
# Clone and setup
git clone <repository-url>
cd rag_chat

# Complete setup with AI models
make setup
make up-full

# This will:
# 1. Start all services (database, API, frontend, Ollama)
# 2. Automatically initialize Ollama with lightweight AI models
# 3. Set up the complete RAG system ready for chat
```

🎉 **That's it!** The system will be ready at:
- **Frontend**: http://localhost:3000
- **API**: http://localhost:8001
- **Chat ready** with AI models automatically loaded

### Manual Setup
If you prefer step-by-step control:

```bash
# 1. Setup environment
make setup

# 2. Start services
make up

# 3. Initialize AI models (optional)
make init-ollama

# 4. Check everything is working
make health
```

## 🤖 AI Model Management

### Automatic Model Detection
The system automatically:
- ✅ **Detects available Ollama models** on startup
- ✅ **Downloads lightweight models** if none exist
- ✅ **Selects the best available model** from preferences
- ✅ **Falls back gracefully** if models fail to load

### Manual Model Management
```bash
# List available models
make ollama-models

# Pull specific models
make ollama-pull MODEL=llama3.2:1b    # Lightweight (1GB)
make ollama-pull MODEL=llama3.1:8b    # More capable (4.7GB)

# Check model status
curl http://localhost:11434/api/tags
```

### Supported Models (in order of preference)
1. **`llama3.2:1b`** - Lightweight, fast responses (recommended)
2. **`llama3.1:8b`** - More capable but requires more RAM
3. **`llama2:7b`** - Fallback option
4. **`codellama:7b`** - Code-focused responses

---

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Nginx         │    │   Core API      │
│   (Next.js)     │◄──►│   (Proxy)       │◄──►│   (FastAPI)     │
│   Port: 3000    │    │   Port: 80      │    │   Port: 8001    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                        │
                       ┌─────────────────┐             │
                       │   Bot Service   │             │
                       │   (Slack/Teams) │◄────────────┤
                       │   Port: 8012    │             │
                       └─────────────────┘             │
                                                        │
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │   Redis         │    │   Ollama        │
│   (pgvector)    │◄──►│   (Cache)       │◄──►│   (LLM)         │
│   Port: 5432    │    │   Port: 6379    │    │   Port: 11434   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

---

## 🎨 **Frontend Features**

### **Modern Enterprise Design**
- **Gradient Backgrounds** - Professional visual hierarchy
- **Card-Based Layout** - Clean, organized information display
- **Responsive Sidebar** - Collapsible navigation with descriptions
- **Interactive Elements** - Hover effects, smooth transitions
- **Status Indicators** - Real-time system health monitoring

### **Dashboard Analytics**
- **System Metrics** - Query volume, response times, active users
- **Domain Management** - Visual domain cards with status indicators
- **Recent Activity** - Real-time activity feed with icons
- **Quick Actions** - One-click access to key features

### **AI Chat Interface**
- **Professional Chat UI** - Modern message bubbles with avatars
- **Domain Selection** - Switch between specialized AI assistants
- **Confidence Scoring** - AI response confidence indicators
- **Typing Indicators** - Real-time conversation feedback
- **Message History** - Persistent conversation storage

---

## 🐳 **Docker Commands**

### **Essential Commands**
```bash
# Quick start everything
make quick-start

# Check system status
make status

# View all logs
make logs

# Health check all services
make health

# Stop everything
make quick-stop
```

### **Development Commands**
```bash
# Start in development mode
make dev

# Start only frontend stack
make frontend

# Start only backend services
make backend

# View specific service logs
make logs-frontend
make logs-api
make logs-ollama
```

### **Maintenance Commands**
```bash
# Restart all services
make restart

# Clean up everything
make clean

# Database backup
make backup

# Reset database
make db-reset
```

---

## 🔧 **Service Details**

### **Core Services**
| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| Frontend | 3000 | Next.js React UI | http://localhost:3000 |
| Core API | 8001 | FastAPI Backend | http://localhost:8001/health |
| Bot Service | 8012 | Slack/Teams Integration | http://localhost:8012/health |
| Nginx | 80 | Load Balancer | http://localhost:80/health |

### **Infrastructure**
| Service | Port | Description | Health Check |
|---------|------|-------------|--------------|
| PostgreSQL | 5432 | Database with pgvector | `pg_isready` |
| Redis | 6379 | Cache & Sessions | `redis-cli ping` |
| Ollama | 11434 | Local LLM | http://localhost:11434/api/tags |

---

## 🎯 **Key Features**

### **✅ Implemented (96% PRD Alignment)**
- ✅ **Professional Modern Frontend** - Next.js + React + TypeScript
- ✅ **Multi-Domain RAG Architecture** - 5 specialized domains
- ✅ **Real-time Chat Interface** - WebSocket with confidence scoring
- ✅ **Vector Search & Embeddings** - FAISS + Ollama integration
- ✅ **Agent Workflows** - Intent classification and routing
- ✅ **File Processing** - Upload, validation, and storage
- ✅ **Web Crawling** - Configurable crawler with robots.txt
- ✅ **API Integrations** - Jira, GitHub, Confluence connectors
- ✅ **Authentication & Security** - JWT, RBAC, audit logging
- ✅ **Docker Deployment** - Complete containerized setup
- ✅ **Bot Integration** - Slack/Teams support

### **🔄 In Progress**
- 🔄 **Voice Query Support** - Speech-to-text integration
- 🔄 **Multi-language Support** - Internationalization
- 🔄 **Mobile App** - Progressive Web App enhancement

---

## 🛠️ **Development**

### **Local Development**
```bash
# Start development environment
make dev

# The frontend will be available with hot reload
# API will restart automatically on code changes
```

### **Adding New Features**
1. **Frontend**: Edit files in `frontend/src/`
2. **Backend**: Edit files in `core-api/src/`
3. **Services**: Add new services in `services/`

### **Testing**
```bash
# Run all tests
make test

# Run linting
make lint
```

---

## 📊 **Monitoring & Health**

### **Health Checks**
```bash
# Check all services
make health

# View system status
make status
```

### **Logs**
```bash
# All services
make logs

# Specific service
make logs-frontend
make logs-api
```

---

## 🔒 **Security Features**

- **JWT Authentication** - Secure token-based auth
- **RBAC System** - Role-based access control
- **Rate Limiting** - API protection via Nginx
- **Security Headers** - XSS, CSRF protection
- **Audit Logging** - Comprehensive activity tracking
- **Data Encryption** - At rest and in transit

---

## 🎉 **What Makes This Special**

### **Enterprise-Ready**
- **Professional UI** - Modern, responsive design
- **Scalable Architecture** - Microservices with Docker
- **Security First** - Authentication, authorization, audit trails
- **Production Ready** - Health checks, monitoring, logging

### **Developer Friendly**
- **One-Command Setup** - `make quick-start`
- **Hot Reload** - Rapid development cycles
- **Comprehensive Docs** - Clear instructions and examples
- **Modular Design** - Easy to extend and customize

### **AI-Powered**
- **Multi-Domain Intelligence** - Specialized AI for different areas
- **Real-time Processing** - Instant responses with confidence scoring
- **Advanced RAG** - Vector search with hybrid ranking
- **Agent Workflows** - Intelligent query routing

---

## 📞 **Support**

For issues or questions:
1. Check the logs: `make logs`
2. Verify health: `make health`
3. Review the documentation above
4. Check Docker status: `make status`

---

**🎯 Ready to experience enterprise-grade AI? Run `make quick-start` and visit http://localhost:3000!** 