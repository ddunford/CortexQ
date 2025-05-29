"""
Web Scraper Management Routes
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import text, and_, or_
from typing import List, Optional, Dict, Any
from datetime import datetime
import json
import uuid

from dependencies import get_db, get_current_user, require_permission
from auth_utils import AuditLogger

router = APIRouter(prefix="/api/scraper", tags=["scraper-management"])

# ============================================================================
# LIST AND SEARCH SCRAPED PAGES
# ============================================================================

@router.get("/pages")
async def list_scraped_pages(
    current_user: dict = Depends(require_permission("content:read")),
    db: Session = Depends(get_db),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    domain: Optional[str] = Query(None),
    connector_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    blocked_only: bool = Query(False)
):
    """List all scraped pages with filtering and pagination"""
    
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, o.slug
            FROM organization_members om
            JOIN organizations o ON om.organization_id = o.id
            WHERE om.user_id = :user_id AND om.is_active = true
            LIMIT 1
        """),
        {"user_id": current_user["id"]}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with any organization")
    
    org_id = org_result.organization_id
    
    # Build base query
    where_conditions = ["cp.organization_id = :org_id"]
    params = {"org_id": org_id}
    
    # Add filters
    if domain:
        where_conditions.append("od.domain_name = :domain")
        params["domain"] = domain
    
    if connector_id:
        where_conditions.append("cp.connector_id = :connector_id")
        params["connector_id"] = connector_id
    
    if status:
        where_conditions.append("cp.status = :status")
        params["status"] = status
    
    if search:
        where_conditions.append("(cp.title ILIKE :search OR cp.url ILIKE :search OR cp.content ILIKE :search)")
        params["search"] = f"%{search}%"
    
    if blocked_only:
        where_conditions.append("cp.blocked = true")
    
    where_clause = "WHERE " + " AND ".join(where_conditions)
    
    # Get total count
    count_query = f"""
        SELECT COUNT(*)
        FROM crawled_pages cp
        LEFT JOIN organization_domains od ON cp.domain_id = od.id
        {where_clause}
    """
    
    total_count = db.execute(text(count_query), params).fetchone()[0]
    
    # Get paginated results
    offset = (page - 1) * limit
    params.update({"limit": limit, "offset": offset})
    
    results_query = f"""
        SELECT 
            cp.id,
            cp.url,
            cp.title,
            cp.status,
            cp.content_type,
            cp.word_count,
            cp.first_crawled,
            cp.last_crawled,
            cp.depth,
            cp.blocked,
            cp.block_reason,
            cp.metadata,
            od.domain_name,
            c.name as connector_name,
            (SELECT COUNT(*) FROM embeddings e WHERE e.source_id = cp.id AND e.source_type = 'web_page') as embedding_count,
            (SELECT COUNT(*) FROM embeddings e WHERE e.metadata->>'url' = cp.url AND e.source_type = 'image_description') as image_embedding_count
        FROM crawled_pages cp
        LEFT JOIN organization_domains od ON cp.domain_id = od.id
        LEFT JOIN connectors c ON cp.connector_id = c.id
        {where_clause}
        ORDER BY cp.last_crawled DESC NULLS LAST, cp.created_at DESC
        LIMIT :limit OFFSET :offset
    """
    
    results = db.execute(text(results_query), params).fetchall()
    
    # Format results
    pages = []
    for row in results:
        metadata = json.loads(row.metadata) if row.metadata else {}
        visual_content = metadata.get('visual_content', {})
        
        pages.append({
            "id": row.id,
            "url": row.url,
            "title": row.title or "Untitled",
            "status": row.status,
            "content_type": row.content_type,
            "word_count": row.word_count or 0,
            "first_crawled": row.first_crawled.isoformat() if row.first_crawled else None,
            "last_crawled": row.last_crawled.isoformat() if row.last_crawled else None,
            "depth": row.depth,
            "blocked": row.blocked or False,
            "block_reason": row.block_reason,
            "domain": row.domain_name,
            "connector_name": row.connector_name,
            "embedding_count": row.embedding_count or 0,
            "image_embedding_count": row.image_embedding_count or 0,
            "has_images": bool(visual_content.get('screenshots') or visual_content.get('images')),
            "image_count": len(visual_content.get('screenshots', [])) + len(visual_content.get('images', []))
        })
    
    return {
        "pages": pages,
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total_count,
            "pages": (total_count + limit - 1) // limit
        }
    }

# ============================================================================
# GET SINGLE PAGE DETAILS
# ============================================================================

@router.get("/pages/{page_id}")
async def get_scraped_page(
    page_id: str,
    current_user: dict = Depends(require_permission("content:read")),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific scraped page"""
    
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
    
    org_id = org_result.organization_id
    
    # Get page details
    page_result = db.execute(
        text("""
            SELECT 
                cp.*,
                od.domain_name,
                c.name as connector_name,
                c.auth_config as connector_config
            FROM crawled_pages cp
            LEFT JOIN organization_domains od ON cp.domain_id = od.id
            LEFT JOIN connectors c ON cp.connector_id = c.id
            WHERE cp.id = :page_id AND cp.organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    ).fetchone()
    
    if not page_result:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Get embeddings for this page
    embeddings_result = db.execute(
        text("""
            SELECT id, content_text, embedding_model, created_at
            FROM embeddings 
            WHERE source_id = :page_id AND source_type = 'web_page' AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    ).fetchall()
    
    # Get image description embeddings
    image_embeddings_result = db.execute(
        text("""
            SELECT id, content_text, embedding_model, created_at
            FROM embeddings 
            WHERE metadata->>'url' = :url AND source_type = 'image_description' AND organization_id = :org_id
        """),
        {"url": page_result.url, "org_id": org_id}
    ).fetchall()
    
    # Parse metadata
    metadata = json.loads(page_result.metadata) if page_result.metadata else {}
    visual_content = metadata.get('visual_content', {})
    
    return {
        "id": page_result.id,
        "url": page_result.url,
        "title": page_result.title,
        "content": page_result.content,
        "status": page_result.status,
        "content_type": page_result.content_type,
        "word_count": page_result.word_count,
        "first_crawled": page_result.first_crawled.isoformat() if page_result.first_crawled else None,
        "last_crawled": page_result.last_crawled.isoformat() if page_result.last_crawled else None,
        "depth": page_result.depth,
        "blocked": page_result.blocked or False,
        "block_reason": page_result.block_reason,
        "domain": page_result.domain_name,
        "connector_name": page_result.connector_name,
        "metadata": metadata,
        "visual_content": visual_content,
        "embeddings": [
            {
                "id": emb.id,
                "content_preview": emb.content_text[:200] + "..." if len(emb.content_text) > 200 else emb.content_text,
                "model": emb.embedding_model,
                "created_at": emb.created_at.isoformat()
            }
            for emb in embeddings_result
        ],
        "image_embeddings": [
            {
                "id": emb.id,
                "description": emb.content_text,
                "model": emb.embedding_model,
                "created_at": emb.created_at.isoformat()
            }
            for emb in image_embeddings_result
        ]
    }

# ============================================================================
# UPDATE PAGE METADATA
# ============================================================================

@router.put("/pages/{page_id}")
async def update_scraped_page(
    page_id: str,
    update_data: Dict[str, Any],
    current_user: dict = Depends(require_permission("content:write")),
    db: Session = Depends(get_db)
):
    """Update metadata and content for a scraped page"""
    
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
    
    org_id = org_result.organization_id
    
    # Check if page exists
    page_result = db.execute(
        text("""
            SELECT id, title, metadata
            FROM crawled_pages 
            WHERE id = :page_id AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    ).fetchone()
    
    if not page_result:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Extract updatable fields
    allowed_fields = ['title', 'content', 'metadata']
    updates = {}
    
    for field in allowed_fields:
        if field in update_data:
            updates[field] = update_data[field]
    
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    
    # Handle metadata updates
    if 'metadata' in updates:
        current_metadata = json.loads(page_result.metadata) if page_result.metadata else {}
        if isinstance(updates['metadata'], dict):
            current_metadata.update(updates['metadata'])
            updates['metadata'] = json.dumps(current_metadata)
        else:
            updates['metadata'] = json.dumps(updates['metadata'])
    
    # Build update query
    set_clauses = [f"{field} = :{field}" for field in updates.keys()]
    set_clauses.append("updated_at = NOW()")
    
    update_query = f"""
        UPDATE crawled_pages 
        SET {', '.join(set_clauses)}
        WHERE id = :page_id AND organization_id = :org_id
    """
    
    updates.update({"page_id": page_id, "org_id": org_id})
    
    db.execute(text(update_query), updates)
    db.commit()
    
    # Log the update
    AuditLogger.log_event(
        db, "page_update", current_user["id"], "crawled_pages", "update",
        f"Updated scraped page: {page_result.title}",
        {"page_id": page_id, "updated_fields": list(updates.keys())}
    )
    
    return {"success": True, "message": "Page updated successfully"}

# ============================================================================
# BLOCK/UNBLOCK PAGES
# ============================================================================

@router.post("/pages/{page_id}/block")
async def block_page(
    page_id: str,
    block_data: Dict[str, Any],
    current_user: dict = Depends(require_permission("content:write")),
    db: Session = Depends(get_db)
):
    """Block a page from future crawling"""
    
    reason = block_data.get('reason', 'Manually blocked')
    
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
    
    org_id = org_result.organization_id
    
    # Update page to blocked status
    result = db.execute(
        text("""
            UPDATE crawled_pages 
            SET blocked = true, block_reason = :reason, updated_at = NOW()
            WHERE id = :page_id AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id, "reason": reason}
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    
    db.commit()
    
    # Log the action
    AuditLogger.log_event(
        db, "page_block", current_user["id"], "crawled_pages", "update",
        f"Blocked page from crawling: {reason}",
        {"page_id": page_id, "reason": reason}
    )
    
    return {"success": True, "message": "Page blocked successfully"}

@router.post("/pages/{page_id}/unblock")
async def unblock_page(
    page_id: str,
    current_user: dict = Depends(require_permission("content:write")),
    db: Session = Depends(get_db)
):
    """Unblock a page for future crawling"""
    
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
    
    org_id = org_result.organization_id
    
    # Update page to unblocked status
    result = db.execute(
        text("""
            UPDATE crawled_pages 
            SET blocked = false, block_reason = NULL, updated_at = NOW()
            WHERE id = :page_id AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    )
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Page not found")
    
    db.commit()
    
    # Log the action
    AuditLogger.log_event(
        db, "page_unblock", current_user["id"], "crawled_pages", "update",
        f"Unblocked page for crawling",
        {"page_id": page_id}
    )
    
    return {"success": True, "message": "Page unblocked successfully"}

# ============================================================================
# DELETE PAGE
# ============================================================================

@router.delete("/pages/{page_id}")
async def delete_scraped_page(
    page_id: str,
    current_user: dict = Depends(require_permission("content:delete")),
    db: Session = Depends(get_db)
):
    """Delete a scraped page and all associated embeddings"""
    
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
    
    org_id = org_result.organization_id
    
    # Get page details for logging
    page_result = db.execute(
        text("""
            SELECT url, title
            FROM crawled_pages 
            WHERE id = :page_id AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    ).fetchone()
    
    if not page_result:
        raise HTTPException(status_code=404, detail="Page not found")
    
    # Delete associated embeddings first
    db.execute(
        text("""
            DELETE FROM embeddings 
            WHERE source_id = :page_id AND source_type = 'web_page' AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    )
    
    # Delete image description embeddings
    db.execute(
        text("""
            DELETE FROM embeddings 
            WHERE metadata->>'url' = :url AND source_type = 'image_description' AND organization_id = :org_id
        """),
        {"url": page_result.url, "org_id": org_id}
    )
    
    # Delete the page
    db.execute(
        text("""
            DELETE FROM crawled_pages 
            WHERE id = :page_id AND organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    )
    
    db.commit()
    
    # Log the deletion
    AuditLogger.log_event(
        db, "page_delete", current_user["id"], "crawled_pages", "delete",
        f"Deleted scraped page: {page_result.title}",
        {"page_id": page_id, "url": page_result.url}
    )
    
    return {"success": True, "message": "Page deleted successfully"}

# ============================================================================
# RE-SCRAPE PAGE
# ============================================================================

@router.post("/pages/{page_id}/rescrape")
async def rescrape_page(
    page_id: str,
    current_user: dict = Depends(require_permission("content:write")),
    db: Session = Depends(get_db)
):
    """Re-scrape a specific page to update its content"""
    
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
    
    org_id = org_result.organization_id
    
    # Get page details
    page_result = db.execute(
        text("""
            SELECT cp.url, cp.connector_id, c.connector_type, c.auth_config
            FROM crawled_pages cp
            JOIN connectors c ON cp.connector_id = c.id
            WHERE cp.id = :page_id AND cp.organization_id = :org_id
        """),
        {"page_id": page_id, "org_id": org_id}
    ).fetchone()
    
    if not page_result:
        raise HTTPException(status_code=404, detail="Page not found")
    
    try:
        # Import the web scraper
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create connector config
        config = ConnectorConfig(
            id=page_result.connector_id,
            organization_id=org_id,
            domain="general",  # Default domain
            connector_type=page_result.connector_type,
            auth_config=page_result.auth_config or {}
        )
        
        # Create scraper instance
        scraper = WebScraperConnector(config)
        
        # Scrape just this URL
        scraped_data = await scraper._scrape_url_list([page_result.url])
        
        if scraped_data:
            # Log the re-scrape
            AuditLogger.log_event(
                db, "page_rescrape", current_user["id"], "crawled_pages", "update",
                f"Re-scraped page: {page_result.url}",
                {"page_id": page_id, "url": page_result.url}
            )
            
            return {
                "success": True, 
                "message": "Page re-scraped successfully",
                "data": scraped_data[0] if scraped_data else None
            }
        else:
            return {
                "success": False,
                "message": "Failed to re-scrape page"
            }
            
    except Exception as e:
        return {
            "success": False,
            "message": f"Re-scrape failed: {str(e)}"
        } 