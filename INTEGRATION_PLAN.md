# 🔄 Integration Plan: Services → Core API Migration

## 📋 **Overview**
Migrate sophisticated functionality from isolated microservices into the unified Core API while maintaining the simplified 3-service architecture.

## 🎯 **Goals**
- Maintain simplified deployment (3 services)
- Integrate enterprise features from existing services
- Achieve 95% PRD alignment
- Preserve all advanced functionality

---

## 📝 **Phase 1: Database Schema Integration**

### **1.1 Enhanced Database Schema**
Merge schemas from all services into unified schema:

```sql
-- Enhanced Users & RBAC (from auth-service)
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    full_name VARCHAR(255),
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,
    is_superuser BOOLEAN DEFAULT FALSE,
    preferences JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE roles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(50) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB DEFAULT '[]',
    domain_access JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

-- Enhanced Files (from file-service)
CREATE TABLE files (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(255) NOT NULL,
    original_filename VARCHAR(255) NOT NULL,
    content_type VARCHAR(100),
    size_bytes BIGINT,
    file_hash VARCHAR(64) UNIQUE,
    processed BOOLEAN DEFAULT FALSE,
    processing_status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    tags TEXT[],
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Multi-Domain Vector Storage (from vector-service)
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_id UUID REFERENCES files(id) ON DELETE CASCADE,
    domain VARCHAR(50) NOT NULL,
    content_text TEXT NOT NULL,
    embedding vector(384),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Intent Classification (from classification-service)
CREATE TABLE classification_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    query TEXT NOT NULL,
    intent VARCHAR(50) NOT NULL,
    confidence FLOAT NOT NULL,
    domain VARCHAR(50),
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent Workflows (from agent-service) 
CREATE TABLE workflow_executions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_type VARCHAR(50) NOT NULL,
    input_data JSONB NOT NULL,
    output_data JSONB,
    status VARCHAR(20) DEFAULT 'pending',
    confidence FLOAT,
    user_id UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Audit Logging (from audit-service)
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    event_type VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id),
    resource VARCHAR(100),
    action VARCHAR(50),
    event_data JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 📝 **Phase 2: Core API Enhancement**

### **2.1 Authentication & RBAC Integration**
Migrate from `services/infrastructure/auth-service/`:

```python
# Enhanced authentication with RBAC
@app.post("/auth/login")
async def login_enhanced(credentials: LoginRequest, db: Session = Depends(get_db)):
    # From auth-service: comprehensive login with role loading
    user = authenticate_user(db, credentials.username, credentials.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Load user roles and permissions
    user_roles = get_user_roles(db, user.id)
    permissions = get_user_permissions(db, user.id)
    
    # Enhanced JWT with roles/permissions
    access_token = create_access_token({
        "sub": str(user.id),
        "roles": user_roles,
        "permissions": permissions
    })
    
    return {
        "access_token": access_token,
        "user": {
            "id": str(user.id),
            "username": user.username,
            "roles": user_roles,
            "permissions": permissions
        }
    }

# RBAC endpoints
@app.get("/roles")
async def list_roles(current_user: User = Depends(require_admin)):
    # Full RBAC management from auth-service

@app.post("/users/{user_id}/roles/{role_name}")
async def assign_role(user_id: str, role_name: str):
    # Role assignment logic
```

### **2.2 File Processing Enhancement**
Migrate from `services/ingestion/file-service/`:

```python
@app.post("/files/upload")
async def upload_file_enhanced(
    file: UploadFile = File(...),
    domain: str = "general",
    current_user: User = Depends(get_current_user)
):
    # Enhanced file processing with:
    # - Domain classification
    # - Content extraction (PDF, DOCX, etc.)
    # - Automatic embedding generation
    # - Processing queue integration
    
    # Validate file type and size (from file-service)
    validate_file_type(file.filename)
    
    # Extract content based on type
    content = await extract_file_content(file, file.content_type)
    
    # Generate embeddings for the domain
    embeddings = await generate_domain_embeddings(content, domain)
    
    # Store in domain-specific vector index
    await store_embeddings(embeddings, domain, file_record.id)
    
    return {"status": "processed", "domain": domain}
```

### **2.3 RAG Enhancement**
Migrate from `services/query/rag-service/`:

```python
@app.post("/query/rag")
async def rag_query_enhanced(
    request: RAGRequest,
    current_user: User = Depends(get_current_user)
):
    # Multi-domain RAG with agent workflows
    
    # 1. Intent Classification (from classification-service)
    intent = await classify_intent(request.query, request.domain)
    
    # 2. Agent Workflow Routing (from agent-service)  
    if intent.classification == "bug_report":
        result = await execute_bug_workflow(request, intent)
    elif intent.classification == "feature_request":
        result = await execute_feature_workflow(request, intent)
    else:
        result = await execute_general_rag(request)
    
    # 3. Audit logging
    await log_audit_event("rag_query", current_user.id, {
        "query": request.query,
        "intent": intent.classification,
        "confidence": result.confidence
    })
    
    return result
```

---

## 📝 **Phase 3: Frontend Integration**

### **3.1 Enhanced React Frontend**
Update frontend to use new integrated APIs:

```typescript
// Enhanced chat with domain support
const ChatInterface = () => {
  const [domain, setDomain] = useState('general');
  const [user, setUser] = useState(null);
  
  // Load user with roles/permissions
  useEffect(() => {
    loadUserProfile().then(userData => {
      setUser(userData);
      // Set available domains based on permissions
      setAvailableDomains(userData.permissions.domains);
    });
  }, []);
  
  // Enhanced message sending with domain context
  const sendMessage = async (message: string) => {
    const response = await fetch('/api/query/rag', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        query: message,
        domain: domain,
        context: conversationContext
      })
    });
    
    const result = await response.json();
    
    // Display enhanced response with sources, confidence, intent
    setMessages(prev => [...prev, {
      text: result.response,
      sources: result.sources,
      confidence: result.confidence,
      intent: result.intent_classification
    }]);
  };
};
```

---

## 📝 **Phase 4: Migration Execution**

### **4.1 Database Migration**
```bash
# Create migration script
docker compose -f docker-compose.simple.yml exec postgres psql -U admin -d rag_searcher -f enhanced_schema.sql

# Migrate existing data
python scripts/migrate_to_enhanced_schema.py
```

### **4.2 Code Integration**
```bash
# Copy enhanced modules from services
cp services/infrastructure/auth-service/src/auth_utils.py core-api/src/
cp services/query/rag-service/src/rag_processor.py core-api/src/
cp services/query/classification-service/src/classifiers.py core-api/src/
cp services/query/agent-service/src/workflows.py core-api/src/

# Update requirements.txt with all dependencies
cat services/*/requirements.txt | sort | uniq > core-api/requirements.txt
```

### **4.3 Testing & Validation**
```bash
# Test enhanced functionality
pytest core-api/tests/test_rbac.py
pytest core-api/tests/test_multi_domain_rag.py
pytest core-api/tests/test_agent_workflows.py
pytest core-api/tests/test_file_processing.py
```

---

## 🎯 **Expected Outcomes**

### **✅ Benefits**
- **Simplified Deployment**: Still 3 services (Frontend, Core API, Database)
- **Full PRD Compliance**: 95%+ feature alignment
- **Enterprise Ready**: RBAC, audit logging, multi-domain support
- **Maintainable**: Single codebase with all functionality
- **Scalable**: Can still be split back to microservices if needed

### **📊 Port Configuration (Unchanged)**
- Frontend: `3000` (React/Next.js)
- Core API: `8001` (Enhanced FastAPI with all features)
- PostgreSQL: `5432` (Enhanced schema)
- Redis: `6379` (Caching & sessions)

### **🔄 Migration Timeline**
- **Week 1**: Database schema migration
- **Week 2**: Core API enhancement (auth, RBAC, files)
- **Week 3**: RAG & agent integration
- **Week 4**: Frontend updates & testing
- **Week 5**: Production deployment & documentation

---

This plan preserves the simplified architecture while integrating all the sophisticated functionality from the existing microservices, achieving full PRD compliance without operational complexity. 