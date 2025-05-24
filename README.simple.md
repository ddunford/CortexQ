# 🚀 Enterprise RAG System - Simplified Architecture

**A streamlined, production-ready Retrieval-Augmented Generation system with just 3 services.**

## 🏗️ **Architecture Overview**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Core API      │    │   Database      │
│   (Port 3000)   │────│   (Port 8000)   │────│   PostgreSQL    │
│   • Next.js     │    │   • FastAPI     │    │   • pgvector    │
│   • React       │    │   • Auth/RBAC   │    │   • Redis Cache │
│   • Tailwind    │    │   • RAG Engine  │    └─────────────────┘
│   • TypeScript  │    │   • File Upload │
└─────────────────┘    │   • Vector DB   │
                       │   • Chat API    │
                       │   • Admin Tools │
                       └─────────────────┘
```

## ✨ **Features**

### 🎯 **Core Functionality**
- **Unified API**: All backend functionality in one service
- **Modern Frontend**: Clean React interface with TypeScript
- **RAG Processing**: Vector search with FAISS and sentence transformers
- **File Upload**: Support for text files with automatic indexing
- **Real-time Chat**: WebSocket support for live conversations
- **Authentication**: JWT-based user management

### 🔒 **Enterprise Ready**
- **Database**: PostgreSQL with pgvector extension
- **Caching**: Redis for session and query caching
- **Security**: Bcrypt password hashing, JWT tokens
- **Health Checks**: Built-in monitoring endpoints
- **Docker**: Fully containerized deployment

## 🚀 **Quick Start**

### **1. Start the System**
```bash
# Using the simplified compose file
docker-compose -f docker-compose.simple.yml up -d

# Or build and start in one command
docker-compose -f docker-compose.simple.yml up --build
```

### **2. Initialize Database**
```bash
# Connect to PostgreSQL and run the init script
docker exec -it rag_chat-postgres-1 psql -U admin -d rag_searcher -f /docker-entrypoint-initdb.d/init_db.sql
```

### **3. Access the Application**
- **Frontend**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **Default Login**: `admin` / `admin123`

## 📊 **Service Details**

### **Frontend (Next.js - Port 3000)**
- Modern React application with TypeScript
- Tailwind CSS for styling
- Real-time chat interface
- File upload capabilities
- Responsive design

### **Core API (FastAPI - Port 8000)**
**Authentication & Authorization**
- `POST /auth/register` - User registration
- `POST /auth/login` - User login
- `GET /auth/me` - Current user info

**File Management**
- `POST /files/upload` - Upload and process files
- `GET /files` - List user files

**RAG & Chat**
- `POST /query` - Direct RAG queries
- `POST /chat` - Chat with conversation history
- `WebSocket /ws/{session_id}` - Real-time chat

**Administration**
- `GET /health` - Service health check
- `GET /admin/stats` - System statistics

### **Database Layer**
- **PostgreSQL**: Primary data storage with pgvector
- **Redis**: Caching and session management

## 🛠️ **Development**

### **Local Development**
```bash
# Start just the database services
docker-compose -f docker-compose.simple.yml up postgres redis -d

# Run Core API locally
cd core-api
pip install -r requirements.txt
python src/main.py

# Run Frontend locally (in another terminal)
cd frontend
npm install
npm run dev
```

### **Environment Variables**
```env
# Core API
DATABASE_URL=postgresql://admin:password@localhost:5432/rag_searcher
REDIS_URL=redis://localhost:6379
JWT_SECRET=your-super-secret-jwt-key-change-in-production
DEBUG=true

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📈 **Scaling Options**

### **Horizontal Scaling**
```yaml
# Add multiple Core API instances
core-api:
  # ... existing config
  deploy:
    replicas: 3
  
# Add load balancer
nginx:
  image: nginx:alpine
  ports:
    - "80:80"
  # Configure upstream servers
```

### **Add Services as Needed**
- **Vector Service**: Extract vector operations
- **Auth Service**: Separate authentication
- **File Service**: Dedicated file processing
- **Worker Services**: Background job processing

## 🔍 **Monitoring**

### **Health Checks**
```bash
# API Health
curl http://localhost:8000/health

# Frontend Health  
curl http://localhost:3000

# Database Health
docker exec rag_chat-postgres-1 pg_isready -U admin
```

### **System Stats**
```bash
# Get system statistics
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/admin/stats
```

## 🚀 **Production Deployment**

### **1. Environment Setup**
```bash
# Set production environment variables
export DATABASE_URL="postgresql://user:pass@prod-db:5432/rag_searcher"
export REDIS_URL="redis://prod-redis:6379"
export JWT_SECRET="your-production-secret-key"
export DEBUG=false
```

### **2. SSL/TLS**
```yaml
# Add reverse proxy with SSL
nginx:
  image: nginx:alpine
  ports:
    - "443:443"
  volumes:
    - ./ssl:/etc/nginx/ssl
```

### **3. Database Backups**
```bash
# Automated backups
docker exec postgres pg_dump -U admin rag_searcher > backup.sql
```

## 🎯 **Next Steps**

### **Feature Additions**
- **PDF Processing**: Add PDF parser to file upload
- **Advanced RAG**: Integrate with Ollama or OpenAI
- **Multi-Domain**: Support for different knowledge domains
- **Admin Dashboard**: Enhanced administration interface

### **Infrastructure**
- **Kubernetes**: Deploy to Kubernetes cluster
- **Monitoring**: Add Prometheus and Grafana
- **CI/CD**: GitHub Actions or GitLab pipelines
- **Security**: Add OAuth, RBAC, audit logging

## 📝 **Migration from Complex Setup**

If you're coming from the complex multi-service setup:

```bash
# Backup data from existing services
docker exec rag_chat-postgres-1 pg_dump -U admin rag_searcher > migration.sql

# Stop complex services
docker-compose down

# Start simplified services
docker-compose -f docker-compose.simple.yml up -d

# Restore data
docker exec -i rag_chat-postgres-1 psql -U admin rag_searcher < migration.sql
```

## 🤝 **Contributing**

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test with `docker-compose -f docker-compose.simple.yml up --build`
5. Submit a pull request

## 📄 **License**

MIT License - see LICENSE file for details.

---

**🎉 Much simpler, much more manageable!** This architecture gives you all the core RAG functionality without the complexity of 12+ services. 