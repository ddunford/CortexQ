"""
RAG Service - Main Application
Dedicated Retrieval-Augmented Generation service for intelligent response generation
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from config import settings
from database import get_db, init_database, check_database_health
from models import (
    RAGRequest, RAGResponse, RAGBatchRequest, RAGBatchResponse,
    DomainSearchRequest, CrossDomainSearchRequest, SearchResponse,
    RAGStats, HealthResponse, CacheStatus, FeedbackRequest,
    RAGExecution, SourceQuality
)
from rag_processor import RAGProcessor

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="RAG Service",
    description="Dedicated Retrieval-Augmented Generation service for intelligent response generation",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global RAG processor instance
rag_processor = RAGProcessor()


@app.on_event("startup")
async def startup_event():
    """Initialize service on startup"""
    logger.info("Starting RAG Service...")
    
    try:
        # Initialize database
        init_database()
        logger.info("Database initialized successfully")
        
        # Test external service connections
        await test_external_services()
        
        logger.info(f"RAG Service v{settings.SERVICE_VERSION} started successfully")
        
    except Exception as e:
        logger.error(f"Failed to start service: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown"""
    logger.info("Shutting down RAG Service...")
    
    # Close RAG processor HTTP clients
    await rag_processor.close()
    
    logger.info("RAG Service shutdown complete")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Service health check"""
    
    # Check database health
    db_healthy = check_database_health()
    
    # Check external service connections
    external_services = await check_external_services()
    
    # Check cache status
    cache_status = await get_cache_status()
    
    # Get performance metrics
    try:
        db = next(get_db())
        performance_metrics = await get_performance_metrics(db)
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        performance_metrics = {"error": str(e)}
    
    status = "healthy" if db_healthy and all(external_services.values()) else "degraded"
    
    return HealthResponse(
        status=status,
        service=settings.SERVICE_NAME,
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        dependencies=external_services,
        cache_status=cache_status,
        performance_metrics=performance_metrics
    )


@app.post("/generate", response_model=RAGResponse)
async def generate_response(
    request: RAGRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Generate RAG response for a query"""
    
    logger.info(f"Processing RAG request: {request.query[:50]}...")
    
    try:
        # Process the RAG request
        response = await rag_processor.process_query(request, db)
        
        # Schedule background tasks for analytics
        background_tasks.add_task(
            update_analytics, 
            str(response.execution_id), 
            request.domain, 
            response.confidence
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error processing RAG request: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process RAG request: {str(e)}"
        )


@app.post("/batch", response_model=RAGBatchResponse)
async def batch_generate(
    request: RAGBatchRequest,
    db: Session = Depends(get_db)
):
    """Process multiple RAG requests in batch"""
    
    logger.info(f"Processing batch of {len(request.queries)} RAG requests...")
    
    try:
        batch_id = request.batch_id or f"batch_{int(datetime.utcnow().timestamp())}"
        responses = []
        successful = 0
        failed = 0
        start_time = datetime.utcnow()
        
        if request.parallel_processing:
            # Process requests in parallel
            tasks = [
                rag_processor.process_query(query, db) 
                for query in request.queries
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                    logger.error(f"Batch request failed: {result}")
                else:
                    responses.append(result)
                    successful += 1
        else:
            # Process requests sequentially
            for query in request.queries:
                try:
                    response = await rag_processor.process_query(query, db)
                    responses.append(response)
                    successful += 1
                except Exception as e:
                    failed += 1
                    logger.error(f"Batch request failed: {e}")
        
        total_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return RAGBatchResponse(
            batch_id=batch_id,
            responses=responses,
            total_queries=len(request.queries),
            successful_queries=successful,
            failed_queries=failed,
            total_processing_time_ms=total_time
        )
        
    except Exception as e:
        logger.error(f"Error processing batch RAG request: {e}")
        raise HTTPException(
            status_code=500, 
            detail=f"Failed to process batch RAG request: {str(e)}"
        )


@app.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Get RAG execution details"""
    
    try:
        execution = db.query(RAGExecution).filter(
            RAGExecution.id == execution_id
        ).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        return {
            "execution_id": str(execution.id),
            "query": execution.query,
            "domain": execution.domain,
            "mode": execution.mode,
            "response_type": execution.response_type,
            "generated_response": execution.generated_response,
            "confidence_score": execution.confidence_score,
            "source_count": execution.source_count,
            "search_time_ms": execution.search_time_ms,
            "generation_time_ms": execution.generation_time_ms,
            "total_time_ms": execution.total_time_ms,
            "cache_hit": execution.cache_hit,
            "created_at": execution.created_at,
            "completed_at": execution.completed_at,
            "search_results": execution.search_results,
            "error_message": execution.error_message
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid execution ID format")
    except Exception as e:
        logger.error(f"Error retrieving execution: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve execution")


@app.get("/stats", response_model=RAGStats)
async def get_stats(
    days: int = Query(7, description="Number of days to analyze"),
    db: Session = Depends(get_db)
):
    """Get RAG service statistics"""
    
    try:
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get executions from the specified period
        executions = db.query(RAGExecution).filter(
            RAGExecution.created_at >= cutoff_date
        ).all()
        
        total_executions = len(executions)
        
        # Calculate average response time
        response_times = [e.total_time_ms for e in executions if e.total_time_ms]
        avg_response_time = sum(response_times) / len(response_times) if response_times else 0
        
        # Calculate cache hit rate
        cache_hits = len([e for e in executions if e.cache_hit])
        cache_hit_rate = (cache_hits / total_executions * 100) if total_executions > 0 else 0
        
        # Domain breakdown
        domain_counts = {}
        for execution in executions:
            domain = execution.domain
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
        
        top_domains = [
            {"domain": domain, "count": count} 
            for domain, count in sorted(domain_counts.items(), key=lambda x: x[1], reverse=True)
        ]
        
        # Response type breakdown
        response_type_counts = {}
        for execution in executions:
            if execution.response_type:
                response_type_counts[execution.response_type] = response_type_counts.get(execution.response_type, 0) + 1
        
        # Confidence distribution
        confidence_distribution = {
            "high (>0.8)": len([e for e in executions if e.confidence_score and e.confidence_score > 0.8]),
            "medium (0.5-0.8)": len([e for e in executions if e.confidence_score and 0.5 <= e.confidence_score <= 0.8]),
            "low (<0.5)": len([e for e in executions if e.confidence_score and e.confidence_score < 0.5]),
        }
        
        return RAGStats(
            total_executions=total_executions,
            avg_response_time_ms=avg_response_time,
            cache_hit_rate=cache_hit_rate,
            top_domains=top_domains,
            response_type_breakdown=response_type_counts,
            confidence_distribution=confidence_distribution
        )
        
    except Exception as e:
        logger.error(f"Error getting RAG stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")


@app.post("/feedback")
async def submit_feedback(
    feedback: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """Submit feedback on RAG response"""
    
    try:
        # Find the execution
        execution = db.query(RAGExecution).filter(
            RAGExecution.id == feedback.execution_id
        ).first()
        
        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")
        
        # Update source quality based on feedback
        if execution.search_results:
            search_results = execution.search_results.get("results", [])
            
            for result in search_results:
                source_id = result.get("metadata", {}).get("file_id")
                domain = result.get("domain", execution.domain)
                
                if source_id:
                    quality = db.query(SourceQuality).filter(
                        SourceQuality.source_id == source_id,
                        SourceQuality.domain == domain
                    ).first()
                    
                    if quality:
                        if feedback.helpful:
                            quality.positive_feedback += 1
                        else:
                            quality.negative_feedback += 1
                        
                        db.commit()
        
        # Log feedback for analytics
        logger.info(f"Feedback received for execution {feedback.execution_id}: helpful={feedback.helpful}")
        
        return {"message": "Feedback submitted successfully"}
        
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit feedback")


@app.get("/cache/status")
async def get_cache_status_endpoint():
    """Get cache status information"""
    
    cache_status = await get_cache_status()
    return cache_status


@app.delete("/cache/clear")
async def clear_cache():
    """Clear RAG response cache"""
    
    try:
        if rag_processor.cache_enabled:
            # Get all cache keys
            keys = rag_processor.redis_client.keys("rag_response:*")
            if keys:
                rag_processor.redis_client.delete(*keys)
                logger.info(f"Cleared {len(keys)} cache entries")
                return {"message": f"Cleared {len(keys)} cache entries"}
            else:
                return {"message": "Cache is already empty"}
        else:
            return {"message": "Cache is not enabled"}
            
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail="Failed to clear cache")


async def test_external_services():
    """Test connections to external services"""
    
    logger.info("Testing external service connections...")
    
    # Test vector service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.VECTOR_SERVICE_URL}/health")
            if response.status_code == 200:
                logger.info("Vector service connection: OK")
            else:
                logger.warning(f"Vector service returned status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Vector service connection failed: {e}")
    
    # Test classification service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{settings.CLASSIFICATION_SERVICE_URL}/health")
            if response.status_code == 200:
                logger.info("Classification service connection: OK")
            else:
                logger.warning(f"Classification service returned status: {response.status_code}")
    except Exception as e:
        logger.warning(f"Classification service connection failed: {e}")


async def check_external_services() -> Dict[str, str]:
    """Check health of external services"""
    
    services = {}
    
    # Check vector service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.VECTOR_SERVICE_URL}/health")
            services["vector_service"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services["vector_service"] = "unhealthy"
    
    # Check classification service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.CLASSIFICATION_SERVICE_URL}/health")
            services["classification_service"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services["classification_service"] = "unhealthy"
    
    # Check agent service
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{settings.AGENT_SERVICE_URL}/health")
            services["agent_service"] = "healthy" if response.status_code == 200 else "unhealthy"
    except:
        services["agent_service"] = "unhealthy"
    
    return services


async def get_cache_status() -> CacheStatus:
    """Get cache status information"""
    
    if not rag_processor.cache_enabled:
        return CacheStatus(
            enabled=False,
            hit_rate=0.0,
            total_entries=0,
            memory_usage_mb=0.0
        )
    
    try:
        # Get cache info
        cache_info = rag_processor.redis_client.info("memory")
        memory_usage = cache_info.get("used_memory", 0) / 1024 / 1024  # Convert to MB
        
        # Count cache entries
        cache_keys = rag_processor.redis_client.keys("rag_response:*")
        total_entries = len(cache_keys)
        
        # Calculate hit rate (simplified)
        hit_rate = 0.0  # Would need to track hits/misses for accurate calculation
        
        return CacheStatus(
            enabled=True,
            hit_rate=hit_rate,
            total_entries=total_entries,
            memory_usage_mb=memory_usage
        )
        
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return CacheStatus(
            enabled=True,
            hit_rate=0.0,
            total_entries=0,
            memory_usage_mb=0.0
        )


async def get_performance_metrics(db: Session) -> Dict[str, Any]:
    """Get performance metrics"""
    
    try:
        # Get recent executions (last 24 hours)
        from datetime import timedelta
        cutoff = datetime.utcnow() - timedelta(hours=24)
        
        recent_executions = db.query(RAGExecution).filter(
            RAGExecution.created_at >= cutoff
        ).all()
        
        if not recent_executions:
            return {"message": "No recent executions"}
        
        # Calculate metrics
        response_times = [e.total_time_ms for e in recent_executions if e.total_time_ms]
        search_times = [e.search_time_ms for e in recent_executions if e.search_time_ms]
        generation_times = [e.generation_time_ms for e in recent_executions if e.generation_time_ms]
        
        return {
            "total_executions_24h": len(recent_executions),
            "avg_response_time_ms": sum(response_times) / len(response_times) if response_times else 0,
            "avg_search_time_ms": sum(search_times) / len(search_times) if search_times else 0,
            "avg_generation_time_ms": sum(generation_times) / len(generation_times) if generation_times else 0,
            "cache_hit_rate": len([e for e in recent_executions if e.cache_hit]) / len(recent_executions) * 100 if recent_executions else 0,
            "error_rate": len([e for e in recent_executions if e.error_message]) / len(recent_executions) * 100 if recent_executions else 0
        }
        
    except Exception as e:
        logger.error(f"Error calculating performance metrics: {e}")
        return {"error": str(e)}


async def update_analytics(execution_id: str, domain: str, confidence: float):
    """Update analytics in background"""
    
    try:
        # Here you could add:
        # - Analytics tracking
        # - Machine learning model updates
        # - External system notifications
        # - Performance monitoring
        
        logger.debug(f"Analytics updated for execution {execution_id}")
        
    except Exception as e:
        logger.error(f"Error updating analytics: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    ) 