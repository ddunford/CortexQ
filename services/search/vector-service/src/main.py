"""
Vector Index Service - Multi-Domain RAG Architecture
Handles embedding generation and vector similarity search for multiple domains.
"""

import os
import uuid
import asyncio
from typing import List, Optional, Dict, Any
from datetime import datetime

import uvicorn
import numpy as np
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from config import get_settings
from database import get_db, EmbeddingRecord
from embedding_service import EmbeddingService
from vector_stores.multi_domain_store import MultiDomainVectorStore
from domains.domain_config import DomainConfigManager

# Initialize FastAPI app
app = FastAPI(
    title="Multi-Domain Vector Index Service",
    description="Handles embedding generation and vector similarity search across multiple domains",
    version="0.2.0"
)

# Global instances
settings = get_settings()
embedding_service = EmbeddingService(settings)
multi_domain_store = MultiDomainVectorStore(settings)
domain_config_manager = None

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request/Response Models
class EmbedRequest(BaseModel):
    text: str
    source_type: str = "file"
    source_id: Optional[str] = None
    domain: str = "general"
    metadata: Optional[Dict[str, Any]] = None

class DomainSearchRequest(BaseModel):
    query: str
    top_k: int = 10

class CrossDomainSearchRequest(BaseModel):
    query: str
    domains: List[str]
    top_k: int = 10

class EmbedResponse(BaseModel):
    id: str
    domain: str
    dimension: int
    status: str

class SearchResult(BaseModel):
    id: str
    similarity: float
    content: str
    metadata: Dict[str, Any]
    domain: str

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total_found: int
    query_domain: Optional[str] = None
    searched_domains: List[str]

# Mock user for demonstration (replace with real auth)
class MockUser(BaseModel):
    id: str = "admin"
    allowed_domains: List[str] = ["general", "support", "sales", "engineering", "product"]
    domain_roles: Dict[str, List[str]] = {
        "general": ["admin"],
        "support": ["support_admin"],
        "sales": ["sales_manager"],
        "engineering": ["tech_lead"],
        "product": ["product_director"]
    }

def get_current_user() -> MockUser:
    """Mock user authentication - replace with real auth service"""
    return MockUser()

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global domain_config_manager
    
    print("Initializing Multi-Domain Vector Service...")
    
    # Initialize embedding service
    await embedding_service.initialize()
    print(f"Embedding service initialized with provider: {embedding_service.provider}")
    
    # Initialize multi-domain vector store
    db = next(get_db())
    await multi_domain_store.initialize(db)
    domain_config_manager = DomainConfigManager(db)
    
    print("Multi-Domain Vector Service ready!")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "multi-domain-vector-service",
        "embedding_provider": embedding_service.provider,
        "total_domains": len(multi_domain_store.domain_stores),
        "version": "0.2.0"
    }

@app.get("/domains")
async def list_domains(user: MockUser = Depends(get_current_user)):
    """List all domains accessible to the user"""
    accessible_configs = domain_config_manager.get_user_accessible_domains(user.allowed_domains)
    
    domains = []
    for config in accessible_configs:
        domain_stats = await multi_domain_store.get_domain_stats(config.domain_name)
        domains.append({
            "name": config.domain_name,
            "display_name": config.display_name,
            "description": config.description,
            "vector_count": domain_stats["vector_count"] if domain_stats else 0,
            "user_roles": user.domain_roles.get(config.domain_name, [])
        })
    
    return {"domains": domains}

@app.post("/embed/{domain}", response_model=EmbedResponse)
async def generate_embedding(
    domain: str,
    request: EmbedRequest,
    user: MockUser = Depends(get_current_user),
    db = Depends(get_db)
):
    """Generate embedding for text in a specific domain"""
    # Check domain access
    if domain not in user.allowed_domains:
        raise HTTPException(status_code=403, detail=f"Access denied to domain: {domain}")
    
    # Check write permissions
    if not domain_config_manager.check_user_domain_access(
        user.allowed_domains, user.domain_roles, domain, "write"
    ):
        raise HTTPException(status_code=403, detail=f"Write access denied to domain: {domain}")
    
    try:
        # Generate embedding
        embedding = await embedding_service.generate_embedding(request.text)
        
        # Create embedding record
        embedding_record = EmbeddingRecord(
            id=uuid.uuid4(),
            source_id=uuid.UUID(request.source_id) if request.source_id else None,
            source_type=request.source_type,
            domain=domain,
            content_text=request.text,
            content_hash=embedding_service.get_text_hash(request.text),
            embedding=embedding.tolist(),
            embedding_metadata=request.metadata or {}
        )
        
        db.add(embedding_record)
        db.commit()
        db.refresh(embedding_record)
        
        # Add to domain vector store
        metadata = {
            "content": request.text,
            "source_type": request.source_type,
            "source_id": str(request.source_id) if request.source_id else None,
            "created_at": embedding_record.created_at.isoformat()
        }
        
        # Add user metadata if provided
        if request.metadata:
            metadata.update(request.metadata)
        
        await multi_domain_store.add_embedding(
            domain=domain,
            embedding_id=str(embedding_record.id),
            vector=embedding,
            metadata=metadata
        )
        
        return EmbedResponse(
            id=str(embedding_record.id),
            domain=domain,
            dimension=len(embedding),
            status="success"
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating embedding: {str(e)}")

@app.post("/search/{domain}", response_model=SearchResponse)
async def search_domain(
    domain: str,
    request: DomainSearchRequest,
    user: MockUser = Depends(get_current_user)
):
    """Search within a specific domain"""
    # Check domain access
    if domain not in user.allowed_domains:
        raise HTTPException(status_code=403, detail=f"Access denied to domain: {domain}")
    
    try:
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)
        
        # Search domain
        results = await multi_domain_store.search_domain(domain, query_embedding, request.top_k)
        
        # Format results
        formatted_results = [
            SearchResult(
                id=result["id"],
                similarity=result["similarity"],
                content=result["metadata"].get("content", ""),
                metadata=result["metadata"],
                domain=result["domain"]
            )
            for result in results
        ]
        
        return SearchResponse(
            results=formatted_results,
            total_found=len(formatted_results),
            query_domain=domain,
            searched_domains=[domain]
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error searching domain: {str(e)}")

@app.post("/search/cross-domain", response_model=SearchResponse)
async def search_cross_domain(
    request: CrossDomainSearchRequest,
    user: MockUser = Depends(get_current_user)
):
    """Search across multiple domains"""
    # Filter to accessible domains
    accessible_domains = [d for d in request.domains if d in user.allowed_domains]
    
    if not accessible_domains:
        raise HTTPException(status_code=403, detail="Access denied to all requested domains")
    
    try:
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(request.query)
        
        # Search multiple domains
        results = await multi_domain_store.search_multiple_domains(
            accessible_domains, query_embedding, request.top_k
        )
        
        # Format results
        formatted_results = [
            SearchResult(
                id=result["id"],
                similarity=result["similarity"],
                content=result["metadata"].get("content", ""),
                metadata=result["metadata"],
                domain=result["domain"]
            )
            for result in results
        ]
        
        return SearchResponse(
            results=formatted_results,
            total_found=len(formatted_results),
            searched_domains=accessible_domains
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in cross-domain search: {str(e)}")

@app.get("/search")
async def auto_search(
    q: str = Query(..., description="Search query"),
    domains: Optional[str] = Query(None, description="Comma-separated list of domains"),
    top_k: int = Query(10, description="Number of results to return"),
    user: MockUser = Depends(get_current_user)
):
    """Auto-search across user's accessible domains or specified domains"""
    # Parse domains parameter
    if domains:
        requested_domains = [d.strip() for d in domains.split(",")]
        search_domains = [d for d in requested_domains if d in user.allowed_domains]
    else:
        search_domains = user.allowed_domains
    
    if not search_domains:
        raise HTTPException(status_code=403, detail="No accessible domains found")
    
    try:
        # Generate query embedding
        query_embedding = await embedding_service.generate_embedding(q)
        
        # Search domains
        results = await multi_domain_store.search_multiple_domains(
            search_domains, query_embedding, top_k
        )
        
        # Format results
        formatted_results = [
            SearchResult(
                id=result["id"],
                similarity=result["similarity"],
                content=result["metadata"].get("content", ""),
                metadata=result["metadata"],
                domain=result["domain"]
            )
            for result in results
        ]
        
        return SearchResponse(
            results=formatted_results,
            total_found=len(formatted_results),
            searched_domains=search_domains
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in auto-search: {str(e)}")

@app.get("/stats")
async def get_stats(
    domain: Optional[str] = Query(None, description="Specific domain stats"),
    user: MockUser = Depends(get_current_user)
):
    """Get vector store statistics"""
    try:
        if domain:
            # Check domain access
            if domain not in user.allowed_domains:
                raise HTTPException(status_code=403, detail=f"Access denied to domain: {domain}")
            
            stats = await multi_domain_store.get_domain_stats(domain)
            if not stats:
                raise HTTPException(status_code=404, detail=f"Domain '{domain}' not found")
            
            return stats
        else:
            # Return stats for all accessible domains
            all_stats = await multi_domain_store.get_all_stats()
            
            # Filter to user's accessible domains
            accessible_stats = {
                "total_domains": 0,
                "total_vectors": 0,
                "domains": {}
            }
            
            for domain_name, domain_stats in all_stats["domains"].items():
                if domain_name in user.allowed_domains:
                    accessible_stats["domains"][domain_name] = domain_stats
                    accessible_stats["total_domains"] += 1
                    accessible_stats["total_vectors"] += domain_stats["vector_count"]
            
            return accessible_stats
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting stats: {str(e)}")

@app.post("/admin/refresh-domains")
async def refresh_domains(
    user: MockUser = Depends(get_current_user),
    db = Depends(get_db)
):
    """Refresh domain configurations (admin only)"""
    # Check if user has admin access to any domain
    is_admin = any("admin" in roles for roles in user.domain_roles.values())
    if not is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        await multi_domain_store.refresh_domains(db)
        domain_config_manager.refresh_cache()
        
        return {"status": "success", "message": "Domain configurations refreshed"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error refreshing domains: {str(e)}")

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=int(os.getenv("VECTOR_SERVICE_PORT", 8002)),
        reload=False
    ) 