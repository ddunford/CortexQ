"""
Search and Discovery Routes
Provides dedicated search endpoints for the frontend Search & Discovery tab
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel

from dependencies import get_db, get_current_user, require_permission
from auth_utils import PermissionManager, AuditLogger
from rag_processor import RAGRequest, RAGMode

# Initialize router
router = APIRouter(tags=["search"])

# Initialize RAG processor (will be set by main app)
rag_processor = None

logger = logging.getLogger(__name__)


def set_rag_processor(processor):
    """Set the RAG processor instance"""
    global rag_processor
    rag_processor = processor


# ============================================================================
# SEARCH MODELS
# ============================================================================

class SearchRequest(BaseModel):
    """Search request model"""
    query: str
    domain: Optional[str] = None
    domains: Optional[List[str]] = None
    filters: Optional[Dict[str, Any]] = {}
    mode: str = "hybrid"  # simple, hybrid, cross_domain, agent_enhanced
    limit: int = 20
    offset: int = 0
    min_confidence: float = 0.3
    include_content_types: Optional[List[str]] = None
    exclude_content_types: Optional[List[str]] = None


class SearchResult(BaseModel):
    """Search result model"""
    id: str
    title: str
    snippet: str
    content: str
    confidence: float
    score: float
    source_type: str
    content_type: str
    domain: str
    metadata: Dict[str, Any]
    created_at: str
    file_id: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response model"""
    results: List[SearchResult]
    total_found: int
    query: str
    domains_searched: List[str]
    search_time_ms: int
    filters_applied: Dict[str, Any]


# ============================================================================
# SEARCH ENDPOINTS
# ============================================================================

@router.post("", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    current_user: dict = Depends(require_permission("search:read")),
    db: Session = Depends(get_db)
):
    """Advanced search across domain content"""
    import time
    start_time = time.time()
    
    try:
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        # Determine search domains
        search_domains = []
        if request.domains:
            # Validate domain access for each requested domain
            for domain in request.domains:
                if PermissionManager.has_domain_access(db, current_user["id"], domain):
                    search_domains.append(domain)
        elif request.domain:
            # Single domain search
            if PermissionManager.has_domain_access(db, current_user["id"], request.domain):
                search_domains.append(request.domain)
            else:
                raise HTTPException(status_code=403, detail=f"Access denied to domain: {request.domain}")
        else:
            # Get all accessible domains for user from organization_domains
            domain_result = db.execute(
                text("""
                    SELECT DISTINCT od.domain_name
                    FROM organization_domains od
                    WHERE od.organization_id = :organization_id
                    AND od.is_active = true
                """),
                {"organization_id": organization_id}
            )
            search_domains = [row.domain_name for row in domain_result.fetchall()]
        
        if not search_domains:
            return SearchResponse(
                results=[],
                total_found=0,
                query=request.query,
                domains_searched=[],
                search_time_ms=int((time.time() - start_time) * 1000),
                filters_applied=request.filters
            )
        
        # Perform search using RAG processor
        if not rag_processor:
            raise HTTPException(status_code=503, detail="Search service not available")
        
        # Convert search mode
        mode_mapping = {
            "simple": RAGMode.SIMPLE,
            "hybrid": RAGMode.HYBRID,
            "cross_domain": RAGMode.CROSS_DOMAIN,
            "agent_enhanced": RAGMode.AGENT_ENHANCED
        }
        rag_mode = mode_mapping.get(request.mode, RAGMode.HYBRID)
        
        # Create RAG request
        rag_request = RAGRequest(
            query=request.query,
            domain=search_domains[0] if search_domains else "general",
            mode=rag_mode,
            max_results=request.limit,
            confidence_threshold=request.min_confidence,
            user_id=current_user["id"],
            organization_id=organization_id
        )
        
        # Execute search
        if len(search_domains) == 1:
            # Single domain search
            search_results = await rag_processor.vector_store.search(
                request.query, 
                search_domains[0], 
                request.limit, 
                request.min_confidence,
                organization_id
            )
        else:
            # Multi-domain search
            cross_results = await rag_processor.vector_store.cross_domain_search(
                request.query, 
                search_domains, 
                request.limit, 
                request.min_confidence,
                organization_id
            )
            # Flatten results
            search_results = []
            for domain, results in cross_results.items():
                search_results.extend(results)
            # Sort by similarity
            search_results.sort(key=lambda x: x.similarity, reverse=True)
            search_results = search_results[:request.limit]
        
        # Apply content type filters based on frontend filter selections
        content_type_filters = []
        if request.filters and isinstance(request.filters, dict):
            # Map frontend filters to content types
            if request.filters.get("documents", True):
                content_type_filters.extend(["document/file", "application/pdf", "application/vnd.openxmlformats", "text/plain", "text/markdown"])
            if request.filters.get("conversations", True):
                content_type_filters.extend(["chat/user", "chat/assistant", "conversation/session"])
            if request.filters.get("externalData", True):
                content_type_filters.extend(["api/", "external/"])
        
        # If specific content types are requested, use those
        if request.include_content_types:
            content_type_filters = request.include_content_types
        
        # Apply content type filtering
        if content_type_filters or request.exclude_content_types:
            filtered_results = []
            for result in search_results:
                content_type = result.metadata.get("content_type", "").lower()
                
                # Include filter
                if content_type_filters:
                    if not any(ct.lower() in content_type for ct in content_type_filters):
                        continue
                
                # Exclude filter
                if request.exclude_content_types:
                    if any(ct.lower() in content_type for ct in request.exclude_content_types):
                        continue
                
                filtered_results.append(result)
            
            search_results = filtered_results
        
        # Convert to response format
        response_results = []
        for result in search_results:
            # Generate snippet from content
            snippet = result.content[:200] + "..." if len(result.content) > 200 else result.content
            
            # Determine source type and title based on content type
            content_type = result.metadata.get("content_type", "unknown")
            if content_type.startswith("chat/"):
                source_type = "conversation"
                if content_type == "chat/user":
                    title = "User Message"
                elif content_type == "chat/assistant":
                    title = "Assistant Response"
                else:
                    title = f"Chat {content_type.split('/')[-1].title()}"
            else:
                source_type = "document"
                title = result.metadata.get("title", "Document")
            
            response_results.append(SearchResult(
                id=result.source_id,
                title=title,
                snippet=snippet,
                content=result.content,
                confidence=result.similarity,
                score=result.similarity,
                source_type=source_type,
                content_type=content_type,
                domain=result.domain,
                metadata=result.metadata,
                created_at="",  # Would need to fetch from database
                file_id=result.source_id
            ))
        
        # Log search activity
        AuditLogger.log_event(
            db, "search", current_user["id"], "search", "execute",
            f"Searched '{request.query}' in domains: {', '.join(search_domains)}",
            {
                "query": request.query,
                "domains": search_domains,
                "results_count": len(response_results),
                "mode": request.mode
            }
        )
        
        search_time_ms = int((time.time() - start_time) * 1000)
        
        return SearchResponse(
            results=response_results,
            total_found=len(response_results),
            query=request.query,
            domains_searched=search_domains,
            search_time_ms=search_time_ms,
            filters_applied=request.filters
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/suggestions")
async def get_search_suggestions(
    query: str = Query(..., description="Search query for suggestions"),
    domain: Optional[str] = Query(None, description="Domain to search in"),
    limit: int = Query(5, description="Number of suggestions"),
    current_user: dict = Depends(require_permission("search:read")),
    db: Session = Depends(get_db)
):
    """Get search suggestions based on query"""
    try:
        # Get user's organization
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        # Get suggestions from file names and content
        suggestions_query = """
            SELECT DISTINCT f.original_filename as suggestion, 'filename' as type
            FROM files f
            LEFT JOIN organization_domains od ON f.domain_id = od.id
            WHERE f.organization_id = :organization_id
            AND LOWER(f.original_filename) LIKE LOWER(:query)
        """
        params = {"organization_id": organization_id, "query": f"%{query}%"}
        
        if domain:
            suggestions_query += " AND od.domain_name = :domain"
            params["domain"] = domain
        
        suggestions_query += " LIMIT :limit"
        params["limit"] = limit
        
        result = db.execute(text(suggestions_query), params)
        
        suggestions = [row.suggestion for row in result.fetchall()]
        
        return {"suggestions": suggestions}
        
    except Exception as e:
        logger.error(f"Suggestions error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get suggestions: {str(e)}")


@router.get("/stats")
async def get_search_stats(
    domain: Optional[str] = Query(None, description="Domain to get stats for"),
    current_user: dict = Depends(require_permission("search:read")),
    db: Session = Depends(get_db)
):
    """Get search statistics"""
    try:
        # Get user's organization
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        # Get file statistics
        stats_query = """
            SELECT 
                COUNT(*) as total_files,
                COUNT(CASE WHEN processed = true THEN 1 END) as indexed_files,
                SUM(size_bytes) as total_size,
                COUNT(DISTINCT od.domain_name) as domains_count,
                COUNT(DISTINCT content_type) as content_types_count
            FROM files f
            LEFT JOIN organization_domains od ON f.domain_id = od.id
            WHERE f.organization_id = :organization_id
        """
        params = {"organization_id": organization_id}
        
        if domain:
            stats_query += " AND od.domain_name = :domain"
            params["domain"] = domain
        
        result = db.execute(text(stats_query), params).fetchone()
        
        # Get embedding statistics
        embeddings_query = """
            SELECT COUNT(*) as total_embeddings
            FROM embeddings e
            JOIN files f ON e.source_id = f.id
            JOIN organization_domains od ON e.domain_id = od.id
            WHERE f.organization_id = :organization_id
        """
        
        if domain:
            embeddings_query += " AND od.domain_name = :domain"
        
        embeddings_result = db.execute(text(embeddings_query), params).fetchone()
        
        return {
            "total_files": result.total_files or 0,
            "indexed_files": result.indexed_files or 0,
            "total_size_bytes": result.total_size or 0,
            "domains_count": result.domains_count or 0,
            "content_types_count": result.content_types_count or 0,
            "total_embeddings": embeddings_result.total_embeddings or 0,
            "search_enabled": rag_processor is not None
        }
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}") 