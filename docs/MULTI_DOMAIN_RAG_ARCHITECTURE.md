# 🏢 Multi-Domain RAG Architecture

## Overview

This document outlines the architecture for implementing multiple specialized RAG searches within the Enterprise RAG Searcher system. Each domain serves different teams with specialized knowledge bases, access controls, and workflows.

---

## 🎯 **Domain Definitions**

### 1. **Support Domain** (Help Assistant)
- **Target Users**: Customer support teams, technical support, QA engineers
- **Data Sources**: 
  - Bug reports and known issues
  - Troubleshooting guides and runbooks
  - Code repositories and stack traces
  - Product documentation and FAQs
  - Customer conversation history
- **Specialized Workflows**:
  - Bug detection and classification
  - Issue escalation routing
  - Resolution step generation
  - Code error pattern matching

### 2. **Sales Domain** (Product Assistant)
- **Target Users**: Sales teams, account managers, presales engineers
- **Data Sources**:
  - Product feature documentation
  - Competitive analysis and battlecards
  - Compliance and security certifications
  - Pricing models and proposals
  - Case studies and success stories
- **Specialized Workflows**:
  - Feature capability queries
  - Compliance requirement matching
  - Competitive positioning
  - ROI and value proposition generation

### 3. **Engineering Domain** (Dev Assistant)
- **Target Users**: Software engineers, DevOps, technical writers
- **Data Sources**:
  - Technical documentation and APIs
  - Code repositories and examples
  - Architecture decisions and design docs
  - Deployment guides and infrastructure docs
- **Specialized Workflows**:
  - Code example generation
  - Architecture pattern suggestions
  - Best practice recommendations

### 4. **Product Domain** (Product Assistant)
- **Target Users**: Product managers, designers, analysts
- **Data Sources**:
  - Product roadmaps and requirements
  - User research and feedback
  - Analytics and metrics
  - Design systems and guidelines
- **Specialized Workflows**:
  - Feature planning assistance
  - User feedback analysis
  - Roadmap query and planning

---

## 🏗️ **Technical Architecture**

### Option 1: **Domain-Aware Vector Service** (Recommended)

#### Enhanced Vector Service Architecture
```
services/search/vector-service/
├── src/
│   ├── domains/
│   │   ├── support_domain.py      # Support-specific logic
│   │   ├── sales_domain.py        # Sales-specific logic
│   │   ├── engineering_domain.py  # Engineering-specific logic
│   │   └── product_domain.py      # Product-specific logic
│   ├── vector_stores/
│   │   ├── domain_router.py       # Routes queries to appropriate domain
│   │   ├── multi_domain_store.py  # Manages multiple FAISS indices
│   │   └── domain_config.py       # Domain-specific configurations
│   ├── embeddings/
│   │   └── domain_embedder.py     # Domain-aware embedding generation
│   └── search/
│       ├── domain_search.py       # Domain-scoped search
│       └── cross_domain_search.py # Search across domains
```

#### Database Schema Enhancement
```sql
-- Add domain support to existing tables
ALTER TABLE embeddings ADD COLUMN domain VARCHAR(50) DEFAULT 'general';
ALTER TABLE search_queries ADD COLUMN domain VARCHAR(50);
ALTER TABLE users ADD COLUMN allowed_domains TEXT[] DEFAULT ARRAY['general'];

-- Create domain-specific configuration table
CREATE TABLE domain_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    domain_name VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(100),
    description TEXT,
    embedding_model VARCHAR(100),
    similarity_threshold FLOAT DEFAULT 0.7,
    max_results INTEGER DEFAULT 10,
    specialized_prompts JSONB DEFAULT '{}',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert default domains
INSERT INTO domain_configs (domain_name, display_name, description, specialized_prompts) VALUES
('support', 'Support Assistant', 'Customer support and troubleshooting', 
 '{"system_prompt": "You are a support assistant. Focus on troubleshooting and issue resolution."}'),
('sales', 'Sales Assistant', 'Product features and sales enablement',
 '{"system_prompt": "You are a sales assistant. Focus on product capabilities and business value."}'),
('engineering', 'Engineering Assistant', 'Technical documentation and development',
 '{"system_prompt": "You are an engineering assistant. Focus on technical accuracy and best practices."}'),
('product', 'Product Assistant', 'Product management and planning',
 '{"system_prompt": "You are a product assistant. Focus on user needs and product strategy."}'
);
```

### Option 2: **Separate Domain Services**

#### Architecture
```
services/domains/
├── support-rag-service/           # Dedicated support RAG
├── sales-rag-service/             # Dedicated sales RAG  
├── engineering-rag-service/       # Dedicated engineering RAG
└── product-rag-service/           # Dedicated product RAG

services/orchestration/
└── domain-router-service/         # Routes requests to appropriate domain
```

---

## 🔧 **Implementation Plan**

### Phase 1: Domain-Aware Vector Service (Recommended Start)

#### 1. Enhance Vector Service Configuration
```python
# services/search/vector-service/src/config.py
class DomainSettings(BaseModel):
    domain_name: str
    display_name: str
    embedding_model: str = "nomic-embed-text"
    similarity_threshold: float = 0.7
    max_results: int = 10
    faiss_index_path: str
    specialized_prompts: Dict[str, str] = {}

class Settings(BaseSettings):
    # ... existing settings ...
    
    # Domain Configuration
    DOMAINS: Dict[str, DomainSettings] = {
        "support": DomainSettings(
            domain_name="support",
            display_name="Support Assistant",
            faiss_index_path="./vector_index/support",
            specialized_prompts={
                "system_prompt": "You are a support assistant focused on troubleshooting and issue resolution."
            }
        ),
        "sales": DomainSettings(
            domain_name="sales", 
            display_name="Sales Assistant",
            faiss_index_path="./vector_index/sales",
            specialized_prompts={
                "system_prompt": "You are a sales assistant focused on product features and business value."
            }
        )
    }
```

#### 2. Domain Router Implementation
```python
# services/search/vector-service/src/domains/domain_router.py
class DomainRouter:
    def __init__(self, settings: Settings):
        self.domains = {
            name: DomainVectorStore(config) 
            for name, config in settings.DOMAINS.items()
        }
    
    async def route_query(self, query: str, user_domains: List[str], 
                         target_domain: Optional[str] = None) -> str:
        """Route query to appropriate domain(s)"""
        if target_domain and target_domain in user_domains:
            return target_domain
        
        # Auto-detect domain based on query content
        domain_scores = await self.classify_domain(query)
        
        # Return highest scoring domain that user has access to
        for domain, score in sorted(domain_scores.items(), key=lambda x: x[1], reverse=True):
            if domain in user_domains:
                return domain
        
        return "general"  # fallback
```

#### 3. Enhanced API Endpoints
```python
# Enhanced search endpoint with domain support
@app.post("/search/{domain}")
async def domain_search(
    domain: str,
    request: SearchRequest,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Search within a specific domain"""
    # Verify user has access to domain
    if domain not in user.allowed_domains:
        raise HTTPException(status_code=403, detail="Access denied to domain")
    
    # Route to domain-specific search
    results = await domain_router.search_domain(domain, request.query, request.top_k)
    return results

@app.post("/search/cross-domain")
async def cross_domain_search(
    request: CrossDomainSearchRequest,
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Search across multiple domains"""
    accessible_domains = [d for d in request.domains if d in user.allowed_domains]
    results = await domain_router.search_multiple_domains(
        accessible_domains, request.query, request.top_k
    )
    return results
```

### Phase 2: Domain-Specific Data Ingestion

#### Enhanced File Service with Domain Tagging
```python
# services/ingestion/file-service/src/api/upload.py
@app.post("/upload/{domain}")
async def upload_file_to_domain(
    domain: str,
    file: UploadFile = File(...),
    metadata: Dict[str, Any] = Body({}),
    user = Depends(get_current_user),
    db = Depends(get_db)
):
    """Upload file to specific domain"""
    if domain not in user.allowed_domains:
        raise HTTPException(status_code=403, detail="Access denied to domain")
    
    # Add domain metadata
    metadata["domain"] = domain
    metadata["uploaded_by_domain"] = user.primary_domain
    
    # Process file upload
    file_record = await process_file_upload(file, metadata, db)
    
    # Trigger domain-specific processing
    await trigger_domain_processing(file_record.id, domain)
    
    return file_record
```

### Phase 3: Role-Based Domain Access

#### Enhanced User Management
```sql
-- Enhanced users table
ALTER TABLE users ADD COLUMN primary_domain VARCHAR(50) DEFAULT 'general';
ALTER TABLE users ADD COLUMN allowed_domains TEXT[] DEFAULT ARRAY['general'];
ALTER TABLE users ADD COLUMN domain_roles JSONB DEFAULT '{}';

-- Example domain roles structure:
-- {
--   "support": ["user", "admin"],
--   "sales": ["user"],
--   "engineering": ["user", "contributor"]
-- }
```

#### Domain Access Control
```python
# services/infrastructure/auth-service/src/rbac/domain_access.py
class DomainAccessControl:
    @staticmethod
    def check_domain_access(user: User, domain: str, action: str = "read") -> bool:
        """Check if user can access domain with specific action"""
        if domain not in user.allowed_domains:
            return False
        
        domain_roles = user.domain_roles.get(domain, [])
        required_permissions = DOMAIN_PERMISSIONS[domain][action]
        
        return any(role in required_permissions for role in domain_roles)
```

---

## 🎛️ **Domain Configuration Interface**

### Admin Dashboard for Domain Management
```
services/ui/admin-service/src/components/
├── DomainManagement/
│   ├── DomainList.tsx             # List all domains
│   ├── DomainConfig.tsx           # Configure domain settings
│   ├── UserDomainAccess.tsx       # Manage user domain access
│   └── DomainAnalytics.tsx        # Domain usage analytics
```

### Domain-Specific Chat Interface
```
services/ui/chat-api/src/components/
├── DomainSelector.tsx             # Domain selection widget
├── DomainChatInterface.tsx        # Domain-aware chat
└── CrossDomainSearch.tsx          # Search across domains
```

---

## 📊 **Benefits of This Architecture**

### 1. **Specialized Knowledge**
- Each domain has optimized embeddings and search parameters
- Domain-specific prompts and response formatting
- Tailored data sources and ingestion pipelines

### 2. **Access Control**
- Fine-grained permissions per domain
- Role-based access within domains
- Audit trails for domain access

### 3. **Performance Optimization**
- Smaller, focused vector indices per domain
- Faster search within domain scope
- Domain-specific caching strategies

### 4. **Scalability**
- Independent scaling per domain
- Domain-specific resource allocation
- Gradual rollout of new domains

### 5. **Compliance & Security**
- Data isolation between domains
- Domain-specific retention policies
- Compliance controls per domain type

---

## 🚀 **Next Steps**

1. **Immediate**: Enhance vector service with domain support
2. **Short-term**: Implement domain-aware file ingestion
3. **Medium-term**: Build domain-specific chat interfaces
4. **Long-term**: Add advanced cross-domain analytics and optimization

This architecture provides a scalable foundation for multiple specialized RAG systems while maintaining centralized management and consistent user experience. 