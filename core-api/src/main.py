"""
Enterprise RAG API - Main Application
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
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime

# Import configuration and utilities
from sentence_transformers import SentenceTransformer
import redis

# Import our modular components
from dependencies import get_db
from routes import (
    auth_router,
    auth_user_router,
    auth_role_router,
    file_router, 
    web_scraping_router,
    chat_router,
    search_router,
    organization_router,
    domain_templates_router,
    analytics_router,
    user_router,
    debug_router
)
from routes.auth_routes import set_session_manager
from routes.chat_routes import set_rag_processor
from routes.search_routes import set_rag_processor as set_search_rag_processor

# Import core services
from rag_processor import initialize_rag_processor
from auth_utils import SessionManager

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")
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
session_manager = SessionManager(redis_client)

# Initialize session manager in auth routes
set_session_manager(session_manager)

# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global embeddings_model, rag_processor
    
    logger.info("🚀 Starting Enhanced Core API...")
    
    # Initialize embeddings model
    try:
        logger.info("Loading embeddings model...")
        embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
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
    
    # Start background processor
    try:
        from background_processor import start_background_processor
        import asyncio
        asyncio.create_task(start_background_processor())
        logger.info("✅ Background processor started")
    except ImportError:
        logger.warning("⚠️ Background processor not available")
    
    logger.info("🎉 Enhanced Core API started successfully!")
    
    yield
    
    logger.info("🛑 Shutting down Enhanced Core API...")
    
    # Stop background processor
    try:
        from background_processor import stop_background_processor
        stop_background_processor()
        logger.info("✅ Background processor stopped")
    except ImportError:
        pass

# ============================================================================
# APPLICATION SETUP
# ============================================================================

app = FastAPI(
    title="Enhanced Core API - Enterprise RAG Searcher",
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
        "service": "enhanced-core-api",
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
app.include_router(auth_user_router, prefix="/auth/users", tags=["User Management"])
app.include_router(auth_role_router, prefix="/auth/roles", tags=["Role Management"])
app.include_router(file_router, prefix="/files", tags=["File Management"])
app.include_router(web_scraping_router, prefix="/web-scraping", tags=["Web Scraping"])
app.include_router(chat_router, prefix="/chat", tags=["Chat & RAG"])
app.include_router(search_router, prefix="/search", tags=["Search & Discovery"])
app.include_router(organization_router, prefix="/organizations", tags=["Organizations"])
app.include_router(domain_templates_router, prefix="/domain-templates", tags=["Domain Templates"])
app.include_router(analytics_router, prefix="/analytics", tags=["Analytics"])
app.include_router(user_router, prefix="/users", tags=["User Profile"])

# Debug router (only in development)
if DEBUG:
    app.include_router(debug_router, prefix="/debug", tags=["Debug"])
    logger.info("🔧 Debug endpoints enabled")

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