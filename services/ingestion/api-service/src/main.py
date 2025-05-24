"""
API Integration Service - Main Application
Handles connections to external APIs (Jira, GitHub, Confluence, etc.)
"""

import uuid
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
import redis
import logging
import httpx
from pydantic import BaseModel, Field

from config import settings
from models import (
    Base, APIConnector, SyncJob, SyncLog,
    ConnectorCreate, ConnectorUpdate, ConnectorResponse,
    SyncJobCreate, SyncJobResponse, SyncLogResponse,
    HealthResponse
)
from connectors import JiraConnector, GitHubConnector, ConfluenceConnector

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
try:
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

# FastAPI app
app = FastAPI(
    title="API Integration Service",
    description="External API integration and data synchronization service",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Connector registry
CONNECTOR_REGISTRY = {
    "jira": JiraConnector,
    "github": GitHubConnector,
    "confluence": ConfluenceConnector,
}

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database tables"""
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    # Check database
    db_healthy = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_healthy = False
    
    # Check cache
    cache_healthy = True
    if redis_client:
        try:
            redis_client.ping()
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            cache_healthy = False
    else:
        cache_healthy = False
    
    return HealthResponse(
        status="healthy" if db_healthy and cache_healthy else "degraded",
        service="api-integration-service",
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        database_healthy=db_healthy,
        cache_healthy=cache_healthy
    )

@app.post("/connectors", response_model=ConnectorResponse)
async def create_connector(
    connector_data: ConnectorCreate,
    db: Session = Depends(get_db)
):
    """Create a new API connector"""
    
    # Validate connector type
    if connector_data.connector_type not in CONNECTOR_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported connector type: {connector_data.connector_type}"
        )
    
    # Test connection
    connector_class = CONNECTOR_REGISTRY[connector_data.connector_type]
    connector = connector_class(connector_data.config)
    
    try:
        await connector.test_connection()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Connection test failed: {str(e)}"
        )
    
    # Create connector
    db_connector = APIConnector(
        name=connector_data.name,
        connector_type=connector_data.connector_type,
        config=connector_data.config,
        sync_frequency=connector_data.sync_frequency,
        is_active=connector_data.is_active
    )
    
    db.add(db_connector)
    db.commit()
    db.refresh(db_connector)
    
    logger.info(f"Created connector: {connector_data.name}")
    
    return ConnectorResponse(
        id=str(db_connector.id),
        name=db_connector.name,
        connector_type=db_connector.connector_type,
        sync_frequency=db_connector.sync_frequency,
        is_active=db_connector.is_active,
        last_sync=db_connector.last_sync,
        created_at=db_connector.created_at,
        status="active" if db_connector.is_active else "inactive"
    )

@app.get("/connectors", response_model=List[ConnectorResponse])
async def list_connectors(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
):
    """List all API connectors"""
    
    connectors = db.query(APIConnector).offset(skip).limit(limit).all()
    
    return [
        ConnectorResponse(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            sync_frequency=connector.sync_frequency,
            is_active=connector.is_active,
            last_sync=connector.last_sync,
            created_at=connector.created_at,
            status="active" if connector.is_active else "inactive"
        )
        for connector in connectors
    ]

@app.get("/connectors/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    connector_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific connector"""
    
    connector = db.query(APIConnector).filter(APIConnector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    return ConnectorResponse(
        id=str(connector.id),
        name=connector.name,
        connector_type=connector.connector_type,
        sync_frequency=connector.sync_frequency,
        is_active=connector.is_active,
        last_sync=connector.last_sync,
        created_at=connector.created_at,
        status="active" if connector.is_active else "inactive"
    )

@app.put("/connectors/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    connector_id: str,
    connector_data: ConnectorUpdate,
    db: Session = Depends(get_db)
):
    """Update a connector"""
    
    connector = db.query(APIConnector).filter(APIConnector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    # Update fields
    if connector_data.name is not None:
        connector.name = connector_data.name
    if connector_data.config is not None:
        connector.config = connector_data.config
    if connector_data.sync_frequency is not None:
        connector.sync_frequency = connector_data.sync_frequency
    if connector_data.is_active is not None:
        connector.is_active = connector_data.is_active
    
    connector.updated_at = datetime.utcnow()
    
    db.commit()
    db.refresh(connector)
    
    logger.info(f"Updated connector: {connector.name}")
    
    return ConnectorResponse(
        id=str(connector.id),
        name=connector.name,
        connector_type=connector.connector_type,
        sync_frequency=connector.sync_frequency,
        is_active=connector.is_active,
        last_sync=connector.last_sync,
        created_at=connector.created_at,
        status="active" if connector.is_active else "inactive"
    )

@app.delete("/connectors/{connector_id}")
async def delete_connector(
    connector_id: str,
    db: Session = Depends(get_db)
):
    """Delete a connector"""
    
    connector = db.query(APIConnector).filter(APIConnector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    db.delete(connector)
    db.commit()
    
    logger.info(f"Deleted connector: {connector.name}")
    
    return {"message": "Connector deleted successfully"}

@app.post("/connectors/{connector_id}/sync", response_model=SyncJobResponse)
async def trigger_sync(
    connector_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Trigger manual sync for a connector"""
    
    connector = db.query(APIConnector).filter(APIConnector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if not connector.is_active:
        raise HTTPException(status_code=400, detail="Connector is not active")
    
    # Create sync job
    sync_job = SyncJob(
        connector_id=connector.id,
        status="pending",
        started_at=datetime.utcnow()
    )
    
    db.add(sync_job)
    db.commit()
    db.refresh(sync_job)
    
    # Start sync in background
    background_tasks.add_task(run_sync_job, str(sync_job.id))
    
    logger.info(f"Started sync job {sync_job.id} for connector {connector.name}")
    
    return SyncJobResponse(
        id=str(sync_job.id),
        connector_id=str(sync_job.connector_id),
        status=sync_job.status,
        started_at=sync_job.started_at,
        completed_at=sync_job.completed_at,
        records_processed=sync_job.records_processed,
        error_message=sync_job.error_message
    )

@app.get("/connectors/{connector_id}/sync-jobs", response_model=List[SyncJobResponse])
async def list_sync_jobs(
    connector_id: str,
    skip: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db)
):
    """List sync jobs for a connector"""
    
    jobs = db.query(SyncJob).filter(
        SyncJob.connector_id == connector_id
    ).order_by(SyncJob.started_at.desc()).offset(skip).limit(limit).all()
    
    return [
        SyncJobResponse(
            id=str(job.id),
            connector_id=str(job.connector_id),
            status=job.status,
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            error_message=job.error_message
        )
        for job in jobs
    ]

@app.post("/connectors/{connector_id}/test")
async def test_connector(
    connector_id: str,
    db: Session = Depends(get_db)
):
    """Test connector connection"""
    
    connector = db.query(APIConnector).filter(APIConnector.id == connector_id).first()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    connector_class = CONNECTOR_REGISTRY[connector.connector_type]
    connector_instance = connector_class(connector.config)
    
    try:
        result = await connector_instance.test_connection()
        return {"status": "success", "message": "Connection test successful", "details": result}
    except Exception as e:
        return {"status": "error", "message": f"Connection test failed: {str(e)}"}

async def run_sync_job(job_id: str):
    """Run a sync job in the background"""
    
    db = SessionLocal()
    try:
        job = db.query(SyncJob).filter(SyncJob.id == job_id).first()
        if not job:
            logger.error(f"Sync job {job_id} not found")
            return
        
        connector = db.query(APIConnector).filter(APIConnector.id == job.connector_id).first()
        if not connector:
            logger.error(f"Connector {job.connector_id} not found")
            return
        
        # Update job status
        job.status = "running"
        db.commit()
        
        # Get connector instance
        connector_class = CONNECTOR_REGISTRY[connector.connector_type]
        connector_instance = connector_class(connector.config)
        
        # Run sync
        records_processed = 0
        async for data in connector_instance.sync_data():
            # Process data (send to file service for indexing)
            await process_sync_data(data, connector.name)
            records_processed += 1
        
        # Update job completion
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        job.records_processed = records_processed
        
        # Update connector last sync
        connector.last_sync = datetime.utcnow()
        
        db.commit()
        
        logger.info(f"Sync job {job_id} completed. Processed {records_processed} records")
        
    except Exception as e:
        logger.error(f"Sync job {job_id} failed: {e}")
        
        # Update job with error
        job.status = "failed"
        job.completed_at = datetime.utcnow()
        job.error_message = str(e)
        db.commit()
        
    finally:
        db.close()

async def process_sync_data(data: Dict[str, Any], source: str):
    """Process synced data by sending to file service"""
    
    try:
        # Send to file service for processing
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.FILE_SERVICE_URL}/process-external",
                json={
                    "data": data,
                    "source": source,
                    "source_type": "api"
                }
            )
            
            if response.status_code != 200:
                logger.warning(f"Failed to process data from {source}: {response.text}")
                
    except Exception as e:
        logger.error(f"Error processing sync data: {e}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=settings.PORT) 