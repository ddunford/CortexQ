"""
Analytics and Reporting Routes
Extracted from main.py for better code organization
Includes general analytics, classification analytics, RAG analytics, and audit analytics
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from dependencies import get_db, get_current_user, require_permission, require_admin

# Initialize router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Global services (will be set by main app)
classifier = None
rag_processor = None

logger = logging.getLogger(__name__)


def set_services(cls, rp):
    """Set service instances"""
    global classifier, rag_processor
    classifier = cls
    rag_processor = rp


# ============================================================================
# GENERAL ANALYTICS ENDPOINTS
# ============================================================================

@router.get("")
async def get_general_analytics(
    domain_id: Optional[str] = None,
    time_range: Optional[str] = None,
    current_user: dict = Depends(require_permission("analytics:read")),
    db: Session = Depends(get_db)
):
    """Get general analytics dashboard data"""
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
        
        # Calculate time range
        days = 7  # Default
        if time_range == "24h":
            days = 1
        elif time_range == "7d":
            days = 7
        elif time_range == "30d":
            days = 30
        elif time_range == "90d":
            days = 90
        
        # Get basic metrics
        where_clause = "WHERE created_at >= NOW() - INTERVAL '%s days'" % days
        if domain_id:
            where_clause += f" AND domain = '{domain_id}'"
        
        # Total queries from chat sessions
        total_queries_result = db.execute(
            text(f"""
                SELECT COUNT(*) as count
                FROM chat_messages
                {where_clause} AND message_type = 'user'
            """)
        ).fetchone()
        total_queries = total_queries_result.count if total_queries_result else 0
        
        # Active users
        active_users_result = db.execute(
            text(f"""
                SELECT COUNT(DISTINCT user_id) as count
                FROM chat_sessions
                {where_clause}
            """)
        ).fetchone()
        active_users = active_users_result.count if active_users_result else 0
        
        # Average response time from RAG executions
        avg_response_time_result = db.execute(
            text(f"""
                SELECT AVG(processing_time_ms) as avg_time
                FROM rag_executions
                {where_clause}
            """)
        ).fetchone()
        avg_response_time = (avg_response_time_result.avg_time / 1000.0) if avg_response_time_result and avg_response_time_result.avg_time else 0.0
        
        # Success rate from chat messages with confidence
        success_rate_result = db.execute(
            text(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN confidence > 0.5 THEN 1 END) as successful
                FROM chat_messages
                {where_clause} AND message_type = 'assistant' AND confidence IS NOT NULL
            """)
        ).fetchone()
        
        success_rate = 0.0
        if success_rate_result and success_rate_result.total > 0:
            success_rate = success_rate_result.successful / success_rate_result.total
        
        # Top queries from chat messages
        top_queries_result = db.execute(
            text(f"""
                SELECT 
                    content as query,
                    COUNT(*) as count,
                    AVG(confidence) as avg_confidence
                FROM chat_messages
                {where_clause} AND message_type = 'user'
                GROUP BY content
                ORDER BY count DESC
                LIMIT 10
            """)
        ).fetchall()
        
        top_queries = [
            {
                "query": row.query,
                "count": row.count,
                "averageConfidence": float(row.avg_confidence) if row.avg_confidence else 0.0
            }
            for row in top_queries_result
        ]
        
        return {
            "totalQueries": total_queries,
            "activeUsers": active_users,
            "averageResponseTime": round(avg_response_time, 2),
            "successRate": round(success_rate, 3),
            "topQueries": top_queries,
            "timeRange": time_range or "7d",
            "domainId": domain_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get general analytics: {str(e)}")
        return {
            "totalQueries": 0,
            "activeUsers": 0,
            "averageResponseTime": 0.0,
            "successRate": 0.0,
            "topQueries": [],
            "timeRange": time_range or "7d",
            "domainId": domain_id
        }


# ============================================================================
# CLASSIFICATION ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/classification")
async def get_classification_analytics(
    domain: Optional[str] = None,
    days: int = 7,
    current_user: dict = Depends(require_permission("analytics:read")),
    db: Session = Depends(get_db)
):
    """Get intent classification analytics with organization isolation"""
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
        
        if not classifier:
            raise HTTPException(status_code=503, detail="Classification service not available")
        
        return await classifier.get_classification_analytics(db, organization_id, domain, days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get classification analytics: {str(e)}")


# ============================================================================
# RAG ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/rag")
async def get_rag_analytics(
    domain: Optional[str] = None,
    days: int = 7,
    current_user: dict = Depends(require_permission("analytics:read")),
    db: Session = Depends(get_db)
):
    """Get enhanced RAG analytics with mode distribution and performance metrics"""
    try:
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        analytics = await rag_processor.get_analytics(db, domain, days)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RAG analytics: {str(e)}")


# ============================================================================
# AUDIT ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/audit")
async def get_audit_analytics(
    days: int = 7,
    current_user: dict = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get audit event analytics"""
    try:
        result = db.execute(
            text("""
                SELECT 
                    event_type,
                    COUNT(*) as count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM audit_events
                WHERE created_at >= NOW() - INTERVAL '%s days'
                GROUP BY event_type
                ORDER BY count DESC
            """ % days)
        ).fetchall()
        
        # Get total events
        total_result = db.execute(
            text("""
                SELECT COUNT(*) as total
                FROM audit_events
                WHERE created_at >= NOW() - INTERVAL '%s days'
            """ % days)
        ).fetchone()
        
        total_events = total_result.total if total_result else 0
        
        # Get unique users
        users_result = db.execute(
            text("""
                SELECT COUNT(DISTINCT user_id) as unique_users
                FROM audit_events
                WHERE created_at >= NOW() - INTERVAL '%s days'
            """ % days)
        ).fetchone()
        
        unique_users = users_result.unique_users if users_result else 0
        
        # Format event types
        event_types = [
            {
                "event_type": row.event_type,
                "count": row.count,
                "unique_users": row.unique_users,
                "percentage": round((row.count / total_events) * 100, 2) if total_events > 0 else 0
            }
            for row in result
        ]
        
        # Get recent events
        recent_events_result = db.execute(
            text("""
                SELECT 
                    ae.event_type,
                    ae.resource_type,
                    ae.action,
                    ae.description,
                    ae.created_at,
                    u.username
                FROM audit_events ae
                LEFT JOIN users u ON ae.user_id = u.id
                WHERE ae.created_at >= NOW() - INTERVAL '%s days'
                ORDER BY ae.created_at DESC
                LIMIT 20
            """ % days)
        ).fetchall()
        
        recent_events = [
            {
                "event_type": row.event_type,
                "resource_type": row.resource_type,
                "action": row.action,
                "description": row.description,
                "created_at": row.created_at.isoformat(),
                "username": row.username
            }
            for row in recent_events_result
        ]
        
        return {
            "total_events": total_events,
            "unique_users": unique_users,
            "event_types": event_types,
            "recent_events": recent_events,
            "time_range_days": days
        }
        
    except Exception as e:
        logger.error(f"Failed to get audit analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get audit analytics: {str(e)}")


# ============================================================================
# CACHE ANALYTICS ENDPOINTS
# ============================================================================

@router.get("/cache")
async def get_cache_analytics(
    current_user: dict = Depends(require_permission("admin:cache")),
    db: Session = Depends(get_db)
):
    """Get cache performance analytics"""
    try:
        # Get cache statistics from database
        cache_stats_result = db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_entries,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '24 hours' THEN 1 END) as entries_24h,
                    COUNT(CASE WHEN created_at >= NOW() - INTERVAL '7 days' THEN 1 END) as entries_7d,
                    AVG(CASE WHEN hit_count > 0 THEN hit_count END) as avg_hit_count,
                    MAX(hit_count) as max_hit_count,
                    COUNT(CASE WHEN hit_count > 0 THEN 1 END) as used_entries,
                    COUNT(CASE WHEN hit_count = 0 THEN 1 END) as unused_entries
                FROM cached_responses
            """)
        ).fetchone()
        
        # Get cache hit rate over time
        hit_rate_result = db.execute(
            text("""
                SELECT 
                    DATE(created_at) as date,
                    COUNT(*) as total_queries,
                    COUNT(CASE WHEN hit_count > 0 THEN 1 END) as cache_hits
                FROM cached_responses
                WHERE created_at >= NOW() - INTERVAL '30 days'
                GROUP BY DATE(created_at)
                ORDER BY date DESC
                LIMIT 30
            """)
        ).fetchall()
        
        # Calculate hit rates
        hit_rate_data = []
        for row in hit_rate_result:
            hit_rate = (row.cache_hits / row.total_queries) * 100 if row.total_queries > 0 else 0
            hit_rate_data.append({
                "date": row.date.isoformat(),
                "total_queries": row.total_queries,
                "cache_hits": row.cache_hits,
                "hit_rate": round(hit_rate, 2)
            })
        
        # Get domain-wise cache statistics
        domain_stats_result = db.execute(
            text("""
                SELECT 
                    domain,
                    COUNT(*) as total_entries,
                    AVG(hit_count) as avg_hit_count,
                    SUM(hit_count) as total_hits
                FROM cached_responses
                GROUP BY domain
                ORDER BY total_hits DESC
                LIMIT 10
            """)
        ).fetchall()
        
        domain_stats = [
            {
                "domain": row.domain,
                "total_entries": row.total_entries,
                "avg_hit_count": round(float(row.avg_hit_count), 2) if row.avg_hit_count else 0,
                "total_hits": row.total_hits
            }
            for row in domain_stats_result
        ]
        
        # Calculate overall statistics
        total_entries = cache_stats_result.total_entries if cache_stats_result else 0
        used_entries = cache_stats_result.used_entries if cache_stats_result else 0
        unused_entries = cache_stats_result.unused_entries if cache_stats_result else 0
        
        cache_efficiency = (used_entries / total_entries) * 100 if total_entries > 0 else 0
        
        return {
            "total_entries": total_entries,
            "entries_24h": cache_stats_result.entries_24h if cache_stats_result else 0,
            "entries_7d": cache_stats_result.entries_7d if cache_stats_result else 0,
            "used_entries": used_entries,
            "unused_entries": unused_entries,
            "cache_efficiency": round(cache_efficiency, 2),
            "avg_hit_count": round(float(cache_stats_result.avg_hit_count), 2) if cache_stats_result and cache_stats_result.avg_hit_count else 0,
            "max_hit_count": cache_stats_result.max_hit_count if cache_stats_result else 0,
            "hit_rate_over_time": hit_rate_data,
            "domain_statistics": domain_stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get cache analytics: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get cache analytics: {str(e)}")


# ============================================================================
# CACHE MANAGEMENT ENDPOINTS
# ============================================================================

@router.post("/cache/invalidate")
async def invalidate_cache(
    domain: Optional[str] = None,
    current_user: dict = Depends(require_permission("admin:cache")),
    db: Session = Depends(get_db)
):
    """Invalidate cache for a specific domain or all domains"""
    try:
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        if domain:
            # Invalidate cache for specific domain
            rag_processor.invalidate_cache_for_domain(domain)
            message = f"Cache invalidated for domain '{domain}'"
        else:
            # Invalidate all cache
            rag_processor.invalidate_all_cache()
            message = "All cache invalidated"
        
        # Log the action
        from auth_utils import AuditLogger
        AuditLogger.log_event(
            db, "cache_invalidation", current_user["id"], "cache", "delete",
            message,
            {"domain": domain, "action": "manual_invalidation"}
        )
        
        return {"status": "success", "message": message}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to invalidate cache: {str(e)}")


@router.get("/cache/status")
async def get_cache_status(
    current_user: dict = Depends(require_permission("admin:cache")),
    db: Session = Depends(get_db)
):
    """Get cache status and statistics"""
    try:
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        cache_stats = {
            "total_cached_responses": len(rag_processor.response_cache),
            "cache_ttl_seconds": rag_processor.cache_ttl_seconds,
            "similarity_threshold": rag_processor.similarity_threshold_for_cache_update,
            "domains_tracked": len(rag_processor.domain_last_updated),
            "cache_entries_by_domain": {},
            "cache_entries_with_embeddings": 0,
            "cache_entries_with_source_tracking": 0
        }
        
        # Analyze cache entries
        for cache_key, cache_data in rag_processor.response_cache.items():
            domain = cache_data.get("domain", "unknown")
            if domain not in cache_stats["cache_entries_by_domain"]:
                cache_stats["cache_entries_by_domain"][domain] = 0
            cache_stats["cache_entries_by_domain"][domain] += 1
            
            if cache_data.get("query_embedding") is not None:
                cache_stats["cache_entries_with_embeddings"] += 1
            
            if cache_data.get("source_ids"):
                cache_stats["cache_entries_with_source_tracking"] += 1
        
        from datetime import datetime
        return {
            "status": "healthy",
            "cache_statistics": cache_stats,
            "smart_cache_enabled": True,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache status: {str(e)}")


@router.get("/cache/analytics")
async def get_cache_analytics(
    current_user: dict = Depends(require_permission("admin:cache")),
    db: Session = Depends(get_db)
):
    """Get detailed cache analytics and performance metrics"""
    try:
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        # Analyze cache hit rates from recent queries
        cache_hit_stats = db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_queries,
                    COUNT(CASE WHEN metadata::text LIKE '%cache_hit%' THEN 1 END) as cache_hits
                FROM rag_executions 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
        ).fetchone()
        
        cache_hit_rate = 0.0
        if cache_hit_stats and cache_hit_stats.total_queries > 0:
            cache_hit_rate = cache_hit_stats.cache_hits / cache_hit_stats.total_queries
        
        # Get average response times for cached vs non-cached
        response_time_stats = db.execute(
            text("""
                SELECT 
                    AVG(CASE WHEN metadata::text LIKE '%cache_hit%' THEN processing_time_ms END) as avg_cached_time,
                    AVG(CASE WHEN metadata::text NOT LIKE '%cache_hit%' OR metadata IS NULL THEN processing_time_ms END) as avg_uncached_time
                FROM rag_executions 
                WHERE created_at >= NOW() - INTERVAL '24 hours'
            """)
        ).fetchone()
        
        avg_cached_time = response_time_stats.avg_cached_time if response_time_stats else 0
        avg_uncached_time = response_time_stats.avg_uncached_time if response_time_stats else 0
        
        return {
            "cache_performance": {
                "hit_rate": round(cache_hit_rate, 3),
                "total_queries_24h": cache_hit_stats.total_queries if cache_hit_stats else 0,
                "cache_hits_24h": cache_hit_stats.cache_hits if cache_hit_stats else 0,
                "avg_cached_response_time_ms": round(avg_cached_time, 2) if avg_cached_time else 0,
                "avg_uncached_response_time_ms": round(avg_uncached_time, 2) if avg_uncached_time else 0,
                "performance_improvement": f"{round((avg_uncached_time / max(avg_cached_time, 1)), 1)}x faster" if avg_cached_time and avg_uncached_time else "N/A"
            },
            "smart_cache_features": {
                "semantic_similarity_enabled": True,
                "cache_enhancement_enabled": True,
                "selective_invalidation_enabled": True,
                "source_tracking_enabled": True
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get cache analytics: {str(e)}")


# Export router
__all__ = ["router"] 