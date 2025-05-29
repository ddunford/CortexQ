"""
CortexQ API - Main Application
Refactored from monolithic 3,663-line file to clean, modular architecture

This file now serves as the application entry point with:
- FastAPI app initialization
- Router registration
- Service initialization
- Middleware configuration
- Application lifecycle management

All business logic has been extracted to dedicated modules:
- models/ - Pydantic models
- dependencies/ - FastAPI dependencies
- routes/ - API endpoints organized by domain
"""

import os
import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Import configuration and utilities
from sentence_transformers import SentenceTransformer
import redis

# Import our modular components
from dependencies import get_db
from routes import (
    auth_router,
    file_router, 
    web_scraping_router,
    sources_router,
    chat_router,
    search_router,
    organization_router,
    domain_templates_router,
    analytics_router,
    user_router,
    debug_router,
    connectors_router
)
from routes.auth_routes import set_session_manager
from routes.chat_routes import set_rag_processor
from routes.search_routes import set_rag_processor as set_search_rag_processor
from routes.scraper_management_routes import router as scraper_management_router

# Import core services
from rag_processor import initialize_rag_processor
from auth_utils import SessionManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/cortexq")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Redis setup
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
    logger.info("✅ Redis connected successfully")
except Exception as e:
    redis_client = None
    logger.warning(f"⚠️ Redis not available: {e}")

# Global instances
embeddings_model = None
rag_processor = None
background_job_processor = None
session_manager = SessionManager(redis_client)

# Initialize session manager in auth routes
set_session_manager(session_manager)

# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global embeddings_model, rag_processor, background_job_processor
    
    logger.info("🚀 Starting CortexQ Core API...")
    
    # Initialize embeddings model
    try:
        logger.info("Loading embeddings model...")
        # Use a 768-dimensional model to match our system configuration
        embeddings_model = SentenceTransformer('all-mpnet-base-v2')  # 768-dimensional model
        logger.info("✅ Embeddings model loaded")
    except Exception as e:
        logger.error(f"❌ Failed to load embeddings model: {e}")
        embeddings_model = None
    
    # Initialize RAG processor
    if embeddings_model:
        try:
            logger.info("Initializing RAG processor...")
            rag_processor = initialize_rag_processor(embeddings_model)
            logger.info("✅ RAG processor initialized")
            
            # Set RAG processor in chat routes
            set_rag_processor(rag_processor)
            
            # Set RAG processor in search routes
            set_search_rag_processor(rag_processor)
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize RAG processor: {e}")
            rag_processor = None
    
    # Initialize background processor
    try:
        from background_processor import BackgroundJobProcessor
        background_job_processor = BackgroundJobProcessor()
        await background_job_processor.initialize()
        logger.info("✅ Background processor initialized")
        
        # Start background processor task
        import asyncio
        asyncio.create_task(background_job_processor.start())
        logger.info("✅ Background processor started")
    except Exception as e:
        logger.error(f"❌ Failed to initialize background processor: {e}")
        background_job_processor = None
    
    # Initialize storage service and pass services to file routes
    try:
        from storage_utils import minio_storage
        from routes.file_routes import set_services
        set_services(background_job_processor, minio_storage, crawler_available=True)
        logger.info("✅ File routes services configured")
    except Exception as e:
        logger.warning(f"⚠️ Could not configure file routes services: {e}")
    
    logger.info("🎉 CortexQ Core API started successfully!")
    
    yield
    
    logger.info("🛑 Shutting down CortexQ Core API...")
    
    # Stop background processor
    if background_job_processor:
        background_job_processor.stop()
        logger.info("✅ Background processor stopped")

# ============================================================================
# APPLICATION SETUP
# ============================================================================

app = FastAPI(
    title="CortexQ Core API - AI-Powered Knowledge Management",
    description="Unified API with RBAC, multi-domain RAG, intent classification, and enterprise features",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Enhanced health check with service status"""
    return {
        "status": "healthy",
        "service": "cortexq-core-api",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "redis": "connected" if redis_client else "unavailable",
            "embeddings": "loaded" if embeddings_model else "unavailable",
            "rag_processor": "initialized" if rag_processor else "unavailable"
        }
    }

# ============================================================================
# ROUTER REGISTRATION
# ============================================================================

# Register all routers with appropriate prefixes
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(file_router, prefix="/files", tags=["File Management"])
app.include_router(web_scraping_router, prefix="/web-scraping", tags=["Web Scraping"])
app.include_router(sources_router, prefix="/sources", tags=["Sources"])
app.include_router(chat_router, prefix="/chat", tags=["Chat & RAG"])
app.include_router(search_router, prefix="/search", tags=["Search & Discovery"])
app.include_router(organization_router, prefix="/organizations", tags=["Organizations"])
app.include_router(domain_templates_router, prefix="/domain-templates", tags=["Domain Templates"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
app.include_router(user_router, prefix="/users", tags=["User Profile"])
app.include_router(connectors_router, tags=["Data Source Connectors"])
app.include_router(scraper_management_router, tags=["Scraper Management"])

# Debug router (only in development)
if DEBUG:
    app.include_router(debug_router, prefix="/debug", tags=["Debug"])
    logger.info("🔧 Debug endpoints enabled")

# Add image proxy endpoint for serving MinIO images
@app.get("/api/images/{organization_slug}/{domain}/{year}/{month}/{image_path:path}")
async def proxy_image(
    organization_slug: str,
    domain: str, 
    year: str,
    month: str,
    image_path: str
):
    """Proxy endpoint to serve MinIO images through the public API"""
    try:
        from storage_utils import minio_storage
        import asyncio
        
        # Construct the MinIO object key
        object_key = f"{organization_slug}/{domain}/{year}/{month}/{image_path}"
        logger.info(f"Attempting to serve image: {object_key}")
        
        # Run the synchronous download_file method in a thread pool with timeout
        try:
            file_data = await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, 
                    minio_storage.download_file, 
                    object_key
                ),
                timeout=10.0  # 10 second timeout
            )
        except asyncio.TimeoutError:
            logger.error(f"Timeout downloading image: {object_key}")
            raise HTTPException(status_code=504, detail="Timeout downloading image")
        
        if not file_data:
            logger.warning(f"Image not found in MinIO: {object_key}")
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Determine content type based on file extension
        content_type = "image/png"
        if image_path.lower().endswith('.jpg') or image_path.lower().endswith('.jpeg'):
            content_type = "image/jpeg"
        elif image_path.lower().endswith('.gif'):
            content_type = "image/gif"
        elif image_path.lower().endswith('.webp'):
            content_type = "image/webp"
        elif image_path.lower().endswith('.svg'):
            content_type = "image/svg+xml"
        
        logger.info(f"Successfully serving image: {object_key} ({len(file_data)} bytes, {content_type})")
        
        # Return the image with proper headers
        return Response(
            content=file_data,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                "Access-Control-Allow-Origin": "*",
                "Content-Length": str(len(file_data))
            }
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions (404, 504, etc.)
        raise
    except Exception as e:
        logger.error(f"Unexpected error serving image {object_key}: {e}")
        raise HTTPException(status_code=500, detail="Error serving image")

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info"
    ) 