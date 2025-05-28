"""
Web Scraper/Crawler Management Routes
Comprehensive endpoints for testing, reviewing, and managing web scraping operations
"""

import uuid
import json
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text, desc

from models import (
    CrawlTestRequest, CrawlTestResponse, CrawledPageResponse, 
    CrawlSessionResponse, CrawlStatsResponse, CrawlPreviewResponse,
    CrawlConfigurationRequest, ScheduledCrawlResponse
)
from dependencies import get_db, get_current_user, require_permission
from auth_utils import PermissionManager, AuditLogger
from connectors.web_scraper_connector import WebScraperConnector, ConnectorConfig

# Initialize router
router = APIRouter(tags=["web-crawler"])

logger = logging.getLogger(__name__)


# ============================================================================
# CRAWL TESTING & PREVIEW ENDPOINTS
# ============================================================================

@router.post("/test-crawl", response_model=CrawlTestResponse)
async def test_crawl_configuration(
    request: CrawlTestRequest,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(require_permission("files:write")),
    db: Session = Depends(get_db)
):
    """Test web scraper configuration without saving results"""
    try:
        # Get user's organization context
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
        
        organization_id = str(org_result.organization_id)
        
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], request.domain):
            raise HTTPException(status_code=403, detail=f"Access denied to domain: {request.domain}")
        
        # Create test connector configuration
        config = ConnectorConfig(
            id=str(uuid.uuid4()),
            name=f"Test Crawl - {datetime.utcnow().isoformat()}",
            type="web_scraper",
            auth_config={
                "start_urls": ",".join(request.start_urls),
                "max_depth": str(request.max_depth),
                "max_pages": str(min(request.max_pages, 50)),  # Limit test crawls
                "delay_ms": str(request.delay_ms),
                "respect_robots": str(request.respect_robots),
                "follow_external": str(request.follow_external),
                "include_patterns": ",".join(request.include_patterns or []),
                "exclude_patterns": ",".join(request.exclude_patterns or []),
                "content_filters": json.dumps(request.content_filters or {}),
                "quality_threshold": str(request.quality_threshold or 0.3)
            }
        )
        
        # Initialize scraper
        scraper = WebScraperConnector(config)
        
        # Test connection first
        connection_test, connection_result = await scraper.test_connection()
        if not connection_test:
            return CrawlTestResponse(
                success=False,
                message="Connection test failed",
                connection_test=connection_result,
                preview=None,
                test_crawl_results=None,
                recommendations=["Check if URLs are accessible", "Verify network connectivity"]
            )
        
        # Generate crawl preview
        preview = await scraper.preview_crawl()
        
        # Perform limited test crawl (max 10 pages)
        test_pages = await scraper.fetch_data()
        test_crawl_results = {
            "pages_found": len(test_pages),
            "sample_pages": test_pages[:5],  # First 5 pages as sample
            "content_types": list(set(page.get('content_type', 'unknown') for page in test_pages)),
            "avg_quality_score": sum(page.get('quality_score', 0) for page in test_pages) / max(len(test_pages), 1),
            "total_content_size": sum(page.get('file_size', 0) for page in test_pages),
            "avg_word_count": sum(page.get('word_count', 0) for page in test_pages) / max(len(test_pages), 1)
        }
        
        # Generate recommendations
        recommendations = _generate_crawl_recommendations(preview, test_crawl_results)
        
        # Log test crawl
        AuditLogger.log_event(
            db, "crawl_test", current_user["id"], "crawl_tests", "create",
            f"Tested crawl configuration for {len(request.start_urls)} URLs",
            {
                "start_urls": request.start_urls,
                "pages_discovered": preview.estimated_pages,
                "test_pages_crawled": len(test_pages),
                "domain": request.domain
            }
        )
        
        return CrawlTestResponse(
            success=True,
            message=f"Test completed successfully. Found {len(test_pages)} pages.",
            connection_test=connection_result,
            preview=CrawlPreviewResponse(
                discovered_urls=preview.discovered_urls[:20],  # Limit for response size
                allowed_urls=preview.allowed_urls[:20],
                blocked_urls=preview.blocked_urls[:10],
                robots_blocked=preview.robots_blocked[:10],
                external_urls=preview.external_urls[:10],
                estimated_pages=preview.estimated_pages,
                estimated_duration=preview.estimated_duration
            ),
            test_crawl_results=test_crawl_results,
            recommendations=recommendations
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error testing crawl configuration: {e}")
        raise HTTPException(status_code=500, detail=f"Test failed: {str(e)}")


@router.get("/preview/{connector_id}", response_model=CrawlPreviewResponse)
async def preview_crawl_configuration(
    connector_id: str,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Preview what URLs would be crawled by an existing connector"""
    try:
        # Get connector configuration
        connector = db.execute(
            text("""
                SELECT c.*, od.organization_id, od.domain_name
                FROM connectors c
                JOIN organization_domains od ON c.domain_id = od.id
                JOIN organization_members om ON od.organization_id = om.organization_id
                WHERE c.id = :connector_id AND om.user_id = :user_id AND om.is_active = true
            """),
            {"connector_id": connector_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found or access denied")
        
        # Create scraper instance
        config = ConnectorConfig(
            id=connector.id,
            name=connector.name,
            type=connector.type,
            auth_config=json.loads(connector.auth_config) if connector.auth_config else {}
        )
        
        scraper = WebScraperConnector(config)
        preview = await scraper.preview_crawl()
        
        return CrawlPreviewResponse(
            discovered_urls=preview.discovered_urls,
            allowed_urls=preview.allowed_urls,
            blocked_urls=preview.blocked_urls,
            robots_blocked=preview.robots_blocked,
            external_urls=preview.external_urls,
            estimated_pages=preview.estimated_pages,
            estimated_duration=preview.estimated_duration
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating crawl preview: {e}")
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


# ============================================================================
# CRAWLED CONTENT REVIEW ENDPOINTS
# ============================================================================

@router.get("/crawled-pages", response_model=List[CrawledPageResponse])
async def list_crawled_pages(
    domain: Optional[str] = Query(None, description="Filter by domain"),
    connector_id: Optional[str] = Query(None, description="Filter by connector"),
    status: Optional[str] = Query(None, description="Filter by status (success, failed, skipped)"),
    min_quality_score: Optional[float] = Query(None, description="Minimum quality score"),
    search_query: Optional[str] = Query(None, description="Search in title and content"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """List crawled pages with filtering and search capabilities"""
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
        
        # Build query with filters
        where_conditions = ["cp.organization_id = :org_id"]
        query_params = {"org_id": organization_id}
        
        if domain:
            where_conditions.append("cp.domain_id = (SELECT id FROM organization_domains WHERE domain_name = :domain)")
            query_params["domain"] = domain
        
        if connector_id:
            where_conditions.append("cp.connector_id = :connector_id")
            query_params["connector_id"] = connector_id
        
        if status:
            where_conditions.append("cp.status = :status")
            query_params["status"] = status
        
        if min_quality_score is not None:
            where_conditions.append("cp.metadata->>'quality_score' >= :min_quality")
            query_params["min_quality"] = str(min_quality_score)
        
        if search_query:
            where_conditions.append("""
                (cp.title ILIKE :search OR cp.content ILIKE :search OR cp.url ILIKE :search)
            """)
            query_params["search"] = f"%{search_query}%"
        
        where_clause = " AND ".join(where_conditions)
        
        # Get total count
        count_result = db.execute(
            text(f"""
                SELECT COUNT(*) as total
                FROM crawled_pages cp
                WHERE {where_clause}
            """),
            query_params
        ).fetchone()
        
        total_count = count_result.total
        
        # Get paginated results
        offset = (page - 1) * limit
        query_params.update({"limit": limit, "offset": offset})
        
        result = db.execute(
            text(f"""
                SELECT 
                    cp.id, cp.connector_id, cp.url, cp.title, cp.content,
                    cp.metadata, cp.first_crawled, cp.last_crawled, cp.content_hash,
                    cp.word_count, cp.status, cp.error_message, cp.depth,
                    cp.content_type, cp.file_size, od.domain_name as domain,
                    c.name as connector_name
                FROM crawled_pages cp
                LEFT JOIN connectors c ON cp.connector_id = c.id
                LEFT JOIN organization_domains od ON cp.domain_id = od.id
                WHERE {where_clause}
                ORDER BY cp.last_crawled DESC
                LIMIT :limit OFFSET :offset
            """),
            query_params
        ).fetchall()
        
        # Format response
        pages = []
        for row in result:
            metadata = json.loads(row.metadata) if row.metadata else {}
            
            pages.append(CrawledPageResponse(
                id=str(row.id),
                connector_id=str(row.connector_id),
                connector_name=row.connector_name or "Unknown",
                url=row.url,
                title=row.title or "",
                content_preview=row.content[:300] + "..." if row.content and len(row.content) > 300 else row.content or "",
                metadata=metadata,
                first_crawled=row.first_crawled.isoformat(),
                last_crawled=row.last_crawled.isoformat(),
                content_hash=row.content_hash,
                word_count=row.word_count or 0,
                status=row.status,
                error_message=row.error_message,
                depth=row.depth or 0,
                content_type=row.content_type,
                file_size=row.file_size or 0,
                domain=row.domain,
                quality_score=float(metadata.get('quality_score', 0)),
                has_changes=True  # TODO: Implement change detection
            ))
        
        # Add pagination info to response headers
        return pages
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing crawled pages: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list crawled pages: {str(e)}")


@router.get("/crawled-pages/{page_id}", response_model=CrawledPageResponse)
async def get_crawled_page_details(
    page_id: str,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Get detailed information about a specific crawled page"""
    try:
        # Get page with organization check
        result = db.execute(
            text("""
                SELECT 
                    cp.id, cp.connector_id, cp.url, cp.title, cp.content,
                    cp.metadata, cp.first_crawled, cp.last_crawled, cp.content_hash,
                    cp.word_count, cp.status, cp.error_message, cp.depth,
                    cp.content_type, cp.file_size, od.domain_name as domain,
                    c.name as connector_name,
                    LENGTH(cp.content) as full_content_length
                FROM crawled_pages cp
                LEFT JOIN connectors c ON cp.connector_id = c.id
                LEFT JOIN organization_domains od ON cp.domain_id = od.id
                JOIN organization_members om ON cp.organization_id = om.organization_id
                WHERE cp.id = :page_id AND om.user_id = :user_id AND om.is_active = true
            """),
            {"page_id": page_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Crawled page not found or access denied")
        
        metadata = json.loads(result.metadata) if result.metadata else {}
        
        return CrawledPageResponse(
            id=str(result.id),
            connector_id=str(result.connector_id),
            connector_name=result.connector_name or "Unknown",
            url=result.url,
            title=result.title or "",
            content_preview=result.content,  # Full content for detail view
            metadata=metadata,
            first_crawled=result.first_crawled.isoformat(),
            last_crawled=result.last_crawled.isoformat(),
            content_hash=result.content_hash,
            word_count=result.word_count or 0,
            status=result.status,
            error_message=result.error_message,
            depth=result.depth or 0,
            content_type=result.content_type,
            file_size=result.file_size or 0,
            domain=result.domain,
            quality_score=float(metadata.get('quality_score', 0)),
            has_changes=False  # TODO: Implement change detection
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crawled page details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get page details: {str(e)}")


@router.delete("/crawled-pages/{page_id}")
async def delete_crawled_page(
    page_id: str,
    current_user: dict = Depends(require_permission("files:delete")),
    db: Session = Depends(get_db)
):
    """Delete a specific crawled page"""
    try:
        # Check if page exists and user has access
        result = db.execute(
            text("""
                SELECT cp.url
                FROM crawled_pages cp
                JOIN organization_members om ON cp.organization_id = om.organization_id
                WHERE cp.id = :page_id AND om.user_id = :user_id AND om.is_active = true
            """),
            {"page_id": page_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Crawled page not found or access denied")
        
        # Delete the page
        db.execute(
            text("DELETE FROM crawled_pages WHERE id = :page_id"),
            {"page_id": page_id}
        )
        
        db.commit()
        
        # Log deletion
        AuditLogger.log_event(
            db, "crawled_page_deletion", current_user["id"], "crawled_pages", "delete",
            f"Deleted crawled page: {result.url}",
            {"page_id": page_id, "url": result.url}
        )
        
        return {"message": "Crawled page deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting crawled page: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete page: {str(e)}")


# ============================================================================
# CRAWL SESSION MANAGEMENT
# ============================================================================

@router.get("/sessions", response_model=List[CrawlSessionResponse])
async def list_crawl_sessions(
    connector_id: Optional[str] = Query(None, description="Filter by connector"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """List crawl sessions with status and progress information"""
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
        
        # TODO: Implement crawl_sessions table and populate this endpoint
        # For now, return mock data based on recent crawl activity
        
        result = db.execute(
            text("""
                SELECT 
                    cp.connector_id,
                    c.name as connector_name,
                    MIN(cp.first_crawled) as session_start,
                    MAX(cp.last_crawled) as session_end,
                    COUNT(*) as pages_crawled,
                    SUM(CASE WHEN cp.status = 'success' THEN 1 ELSE 0 END) as successful_pages,
                    SUM(CASE WHEN cp.status = 'failed' THEN 1 ELSE 0 END) as failed_pages,
                    SUM(cp.file_size) as total_bytes,
                    AVG(CAST(cp.metadata->>'quality_score' AS FLOAT)) as avg_quality
                FROM crawled_pages cp
                LEFT JOIN connectors c ON cp.connector_id = c.id
                WHERE cp.organization_id = :org_id
                  AND (:connector_id IS NULL OR cp.connector_id = :connector_id)
                  AND cp.first_crawled >= :since
                GROUP BY cp.connector_id, c.name
                ORDER BY session_start DESC
                LIMIT :limit OFFSET :offset
            """),
            {
                "org_id": organization_id,
                "connector_id": connector_id,
                "since": datetime.utcnow() - timedelta(days=7),  # Last 7 days
                "limit": limit,
                "offset": (page - 1) * limit
            }
        ).fetchall()
        
        sessions = []
        for row in result:
            duration = (row.session_end - row.session_start).total_seconds()
            
            sessions.append(CrawlSessionResponse(
                session_id=str(uuid.uuid4()),  # Generate session ID
                connector_id=str(row.connector_id),
                connector_name=row.connector_name or "Unknown",
                status="completed",  # Inferred from data
                start_time=row.session_start.isoformat(),
                end_time=row.session_end.isoformat() if row.session_end else None,
                duration_seconds=int(duration),
                pages_discovered=row.pages_crawled,
                pages_processed=row.pages_crawled,
                pages_successful=row.successful_pages,
                pages_failed=row.failed_pages,
                bytes_downloaded=row.total_bytes or 0,
                avg_response_time=duration / max(row.pages_crawled, 1),
                success_rate=row.successful_pages / max(row.pages_crawled, 1),
                avg_quality_score=float(row.avg_quality or 0),
                error_summary=None,
                progress_percentage=100.0
            ))
        
        return sessions
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing crawl sessions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list sessions: {str(e)}")


# ============================================================================
# CRAWL STATISTICS & ANALYTICS
# ============================================================================

@router.get("/stats", response_model=CrawlStatsResponse)
async def get_crawl_statistics(
    connector_id: Optional[str] = Query(None, description="Filter by connector"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Get comprehensive crawl statistics and analytics"""
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
        since_date = datetime.utcnow() - timedelta(days=days)
        
        # Build filters
        where_conditions = ["cp.organization_id = :org_id", "cp.first_crawled >= :since_date"]
        query_params = {"org_id": organization_id, "since_date": since_date}
        
        if connector_id:
            where_conditions.append("cp.connector_id = :connector_id")
            query_params["connector_id"] = connector_id
        
        if domain:
            where_conditions.append("cp.domain_id = (SELECT id FROM organization_domains WHERE domain_name = :domain)")
            query_params["domain"] = domain
        
        where_clause = " AND ".join(where_conditions)
        
        # Get overall statistics
        stats_result = db.execute(
            text(f"""
                SELECT 
                    COUNT(*) as total_pages,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_pages,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_pages,
                    SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped_pages,
                    SUM(file_size) as total_bytes,
                    AVG(word_count) as avg_word_count,
                    AVG(CAST(metadata->>'quality_score' AS FLOAT)) as avg_quality_score,
                    COUNT(DISTINCT connector_id) as unique_connectors,
                    COUNT(DISTINCT domain_id) as unique_domains,
                    MIN(first_crawled) as first_crawl_date,
                    MAX(last_crawled) as last_crawl_date
                FROM crawled_pages cp
                WHERE {where_clause}
            """),
            query_params
        ).fetchone()
        
        # Get content type distribution
        content_types = db.execute(
            text(f"""
                SELECT content_type, COUNT(*) as count
                FROM crawled_pages cp
                WHERE {where_clause}
                GROUP BY content_type
                ORDER BY count DESC
                LIMIT 10
            """),
            query_params
        ).fetchall()
        
        # Get quality score distribution
        quality_distribution = db.execute(
            text(f"""
                SELECT 
                    CASE 
                        WHEN CAST(metadata->>'quality_score' AS FLOAT) >= 0.8 THEN 'High (0.8+)'
                        WHEN CAST(metadata->>'quality_score' AS FLOAT) >= 0.6 THEN 'Medium (0.6-0.8)'
                        WHEN CAST(metadata->>'quality_score' AS FLOAT) >= 0.4 THEN 'Low (0.4-0.6)'
                        ELSE 'Very Low (<0.4)'
                    END as quality_range,
                    COUNT(*) as count
                FROM crawled_pages cp
                WHERE {where_clause} AND metadata->>'quality_score' IS NOT NULL
                GROUP BY quality_range
                ORDER BY quality_range
            """),
            query_params
        ).fetchall()
        
        # Get crawl activity over time (daily)
        daily_activity = db.execute(
            text(f"""
                SELECT 
                    DATE(first_crawled) as crawl_date,
                    COUNT(*) as pages_crawled,
                    SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) as successful_pages
                FROM crawled_pages cp
                WHERE {where_clause}
                GROUP BY DATE(first_crawled)
                ORDER BY crawl_date DESC
                LIMIT 30
            """),
            query_params
        ).fetchall()
        
        # Calculate performance metrics
        total_pages = stats_result.total_pages or 0
        successful_pages = stats_result.successful_pages or 0
        failed_pages = stats_result.failed_pages or 0
        
        success_rate = successful_pages / max(total_pages, 1)
        failure_rate = failed_pages / max(total_pages, 1)
        
        return CrawlStatsResponse(
            total_pages=total_pages,
            successful_pages=successful_pages,
            failed_pages=failed_pages,
            skipped_pages=stats_result.skipped_pages or 0,
            success_rate=success_rate,
            failure_rate=failure_rate,
            total_content_size_mb=round((stats_result.total_bytes or 0) / (1024 * 1024), 2),
            avg_word_count=round(stats_result.avg_word_count or 0, 1),
            avg_quality_score=round(stats_result.avg_quality_score or 0, 3),
            unique_connectors=stats_result.unique_connectors or 0,
            unique_domains=stats_result.unique_domains or 0,
            date_range={
                "start": stats_result.first_crawl_date.isoformat() if stats_result.first_crawl_date else None,
                "end": stats_result.last_crawl_date.isoformat() if stats_result.last_crawl_date else None,
                "days": days
            },
            content_type_distribution=[
                {"type": row.content_type or "unknown", "count": row.count}
                for row in content_types
            ],
            quality_score_distribution=[
                {"range": row.quality_range, "count": row.count}
                for row in quality_distribution
            ],
            daily_activity=[
                {
                    "date": row.crawl_date.isoformat(),
                    "pages_crawled": row.pages_crawled,
                    "successful_pages": row.successful_pages,
                    "success_rate": row.successful_pages / max(row.pages_crawled, 1)
                }
                for row in daily_activity
            ]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting crawl statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def _generate_crawl_recommendations(preview: Any, test_results: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on crawl preview and test results"""
    recommendations = []
    
    # URL discovery recommendations
    if preview.estimated_pages < 5:
        recommendations.append("Consider increasing max_depth or adding more start URLs to discover more content")
    elif preview.estimated_pages > 1000:
        recommendations.append("Consider reducing max_depth or adding exclude patterns to limit scope")
    
    # Blocked URLs recommendations
    if len(preview.blocked_urls) > len(preview.allowed_urls) * 0.5:
        recommendations.append("Many URLs are being blocked - review include/exclude patterns")
    
    # Robots.txt recommendations
    if len(preview.robots_blocked) > 0:
        recommendations.append(f"{len(preview.robots_blocked)} URLs blocked by robots.txt - consider reviewing respect_robots setting")
    
    # Content quality recommendations
    avg_quality = test_results.get('avg_quality_score', 0)
    if avg_quality < 0.5:
        recommendations.append("Low average content quality detected - consider adjusting content filters")
    
    # Performance recommendations
    avg_size = test_results.get('total_content_size', 0) / max(test_results.get('pages_found', 1), 1)
    if avg_size > 1024 * 1024:  # 1MB
        recommendations.append("Large page sizes detected - consider increasing delay between requests")
    
    if not recommendations:
        recommendations.append("Configuration looks good! Ready for full crawl.")
    
    return recommendations


# Export router
__all__ = ["router"] 