"""
Connector API Routes
Handles all data source connector operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import uuid
import re
import asyncio
import logging

# Set up logger for this module
logger = logging.getLogger(__name__)

from dependencies import get_db
from dependencies import get_current_user, require_permission
from schemas.connector_schemas import (
    ConnectorCreate, ConnectorUpdate, ConnectorResponse, 
    ConnectorListResponse, SyncJobResponse, OAuthInitiateRequest,
    OAuthCallbackRequest, ConnectorTestResponse, ConnectorStatsResponse,
    ConnectorType, ConnectorStatus, SyncStatus
)
from services.connector_service import ConnectorService
from services.oauth_service import OAuthService
from models import Connector, SyncJob
from auth_utils import AuditLogger

router = APIRouter(prefix="/domains/{domain_id}/connectors", tags=["connectors"])


def get_connector_service(db: Session = Depends(get_db)) -> ConnectorService:
    """Get connector service instance"""
    oauth_service = OAuthService()  # TODO: Add Redis client
    return ConnectorService(db, oauth_service)


@router.get("/types", response_model=Dict[str, Dict[str, Any]])
async def get_supported_connector_types(
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get list of supported connector types and their capabilities"""
    return connector_service.get_supported_connector_types()


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    domain_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    connector_type: Optional[ConnectorType] = None,
    status: Optional[ConnectorStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """List all connectors for a domain"""
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
    
    organization_id = str(org_result.organization_id)
    
    # Build query filters
    where_conditions = [
        "c.organization_id = :org_id",
        "c.domain_id = :domain_id"
    ]
    params = {
        "org_id": organization_id,
        "domain_id": domain_id,
        "skip": skip,
        "limit": limit
    }
    
    if connector_type:
        where_conditions.append("c.connector_type = :connector_type")
        params["connector_type"] = connector_type.value
    
    # Note: status filter removed since connectors table has no status column
    
    where_clause = " AND ".join(where_conditions)
    
    # Get connectors with stats and domain names
    connectors_query = f"""
        SELECT 
            c.*,
            od.domain_name,
            COUNT(sj.id) as total_sync_jobs,
            MAX(CASE WHEN sj.status = 'completed' THEN sj.completed_at END) as last_successful_sync,
            COUNT(CASE WHEN sj.status = 'failed' THEN 1 END) as failed_sync_jobs
        FROM connectors c
        JOIN organization_domains od ON c.domain_id = od.id
        LEFT JOIN sync_jobs sj ON c.id = sj.connector_id
        WHERE {where_clause}
        GROUP BY c.id, od.domain_name
        ORDER BY c.created_at DESC
        OFFSET :skip LIMIT :limit
    """
    
    connectors = db.execute(text(connectors_query), params).fetchall()
    
    # Get total count
    count_query = f"""
        SELECT COUNT(DISTINCT c.id) as total
        FROM connectors c
        WHERE {where_clause}
    """
    total = db.execute(text(count_query), params).fetchone().total
    
    # Format response
    connector_list = []
    for conn in connectors:
        connector_list.append(ConnectorResponse(
            id=str(conn.id),
            name=conn.name,
            connector_type=conn.connector_type,  # Keep as string, don't convert to enum
            domain=conn.domain_name,
            organization_id=str(conn.organization_id),
            status=ConnectorStatus.PENDING,  # Default status since no status column exists
            is_enabled=conn.is_enabled,
            last_sync_at=conn.last_sync_at,
            last_sync_status=conn.last_sync_status,
            sync_error_message=conn.sync_error_message,
            created_at=conn.created_at,
            updated_at=conn.updated_at
        ))
    
    return ConnectorListResponse(
        connectors=connector_list,
        total=total,
        skip=skip,
        limit=limit
    )


@router.post("", response_model=ConnectorResponse)
async def create_connector(
    domain_id: str,
    connector_data: ConnectorCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Create a new connector"""
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
    
    organization_id = str(org_result.organization_id)
    
    # Check if connector name is unique within domain
    existing = db.execute(
        text("""
            SELECT id FROM connectors 
            WHERE organization_id = :org_id AND domain_id = :domain_id AND name = :name
        """),
        {
            "org_id": organization_id,
            "domain_id": domain_id,
            "name": connector_data.name
        }
    ).fetchone()
    
    if existing:
        raise HTTPException(status_code=400, detail="Connector name already exists in this domain")
    
    # Create connector
    connector_id = str(uuid.uuid4())
    
    db.execute(
        text("""
            INSERT INTO connectors (
                id, organization_id, domain_id, connector_type, name, 
                auth_config, sync_config, mapping_config, is_enabled, created_at, updated_at
            ) VALUES (
                :id, :org_id, :domain_id, :connector_type, :name,
                :auth_config, :sync_config, :mapping_config, :is_enabled, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
        """),
        {
            "id": connector_id,
            "org_id": organization_id,
            "domain_id": domain_id,  # Use the domain_id from URL path
            "connector_type": connector_data.connector_type.value,
            "name": connector_data.name,
            "auth_config": json.dumps(connector_data.auth_config if connector_data.auth_config else {}),
            "sync_config": json.dumps(connector_data.sync_config.dict() if connector_data.sync_config else {}),
            "mapping_config": json.dumps(connector_data.mapping_config.dict() if connector_data.mapping_config else {}),
            "is_enabled": connector_data.is_enabled
        }
    )
    db.commit()
    
    # Fetch created connector with domain name
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name 
            FROM connectors c 
            JOIN organization_domains od ON c.domain_id = od.id 
            WHERE c.id = :id
        """),
        {"id": connector_id}
    ).fetchone()
    
    return ConnectorResponse(
        id=str(connector.id),
        name=connector.name,
        connector_type=ConnectorType(connector.connector_type),
        domain=connector.domain_name,
        organization_id=str(connector.organization_id),
        status=ConnectorStatus.PENDING,  # Default status since no status column exists
        is_enabled=connector.is_enabled,
        auth_config=connector.auth_config,
        sync_config=connector.sync_config,
        mapping_config=connector.mapping_config,
        last_sync_at=connector.last_sync_at,
        last_sync_status=connector.last_sync_status,
        sync_error_message=connector.sync_error_message,
        created_at=connector.created_at,
        updated_at=connector.updated_at
    )


@router.get("/{connector_id}", response_model=ConnectorResponse)
async def get_connector(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get a specific connector"""
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
    
    # Get connector with domain name
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    return ConnectorResponse(
        id=str(connector.id),
        name=connector.name,
        connector_type=ConnectorType(connector.connector_type),
        domain=connector.domain_name,
        organization_id=str(connector.organization_id),
        status=ConnectorStatus.PENDING,  # Default status since no status column exists
        is_enabled=connector.is_enabled,
        auth_config=connector.auth_config,
        sync_config=connector.sync_config,
        mapping_config=connector.mapping_config,
        last_sync_at=connector.last_sync_at,
        last_sync_status=connector.last_sync_status,
        sync_error_message=connector.sync_error_message,
        created_at=connector.created_at,
        updated_at=connector.updated_at
    )


@router.put("/{connector_id}", response_model=ConnectorResponse)
async def update_connector(
    domain_id: str,
    connector_id: str,
    connector_data: ConnectorUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Update a connector"""
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
    
    # Check if connector exists
    existing = db.execute(
        text("""
            SELECT id FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id AND domain_id = :domain_id
        """),
        {
            "connector_id": connector_id,
            "org_id": organization_id,
            "domain_id": domain_id
        }
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    # Build update query
    update_fields = []
    params = {"connector_id": connector_id}
    
    if connector_data.name is not None:
        update_fields.append("name = :name")
        params["name"] = connector_data.name
    
    if connector_data.auth_config is not None:
        update_fields.append("auth_config = :auth_config")
        params["auth_config"] = json.dumps(connector_data.auth_config)
    
    if connector_data.sync_config is not None:
        update_fields.append("sync_config = :sync_config")
        params["sync_config"] = json.dumps(connector_data.sync_config.dict())
    
    if connector_data.mapping_config is not None:
        update_fields.append("mapping_config = :mapping_config")
        params["mapping_config"] = json.dumps(connector_data.mapping_config.dict() if connector_data.mapping_config else {})
    
    if connector_data.is_enabled is not None:
        update_fields.append("is_enabled = :is_enabled")
        params["is_enabled"] = connector_data.is_enabled
    
    if update_fields:
        update_fields.append("updated_at = CURRENT_TIMESTAMP")
        
        query = f"""
            UPDATE connectors 
            SET {', '.join(update_fields)}
            WHERE id = :connector_id
        """
        
        db.execute(text(query), params)
        db.commit()
    
    # Return updated connector
    return await get_connector(domain_id, connector_id, db, current_user)


@router.delete("/{connector_id}")
async def delete_connector(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Delete a connector"""
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
    
    # Check if connector exists
    existing = db.execute(
        text("""
            SELECT id FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id AND domain_id = :domain_id
        """),
        {
            "connector_id": connector_id,
            "org_id": organization_id,
            "domain_id": domain_id
        }
    ).fetchone()
    
    if not existing:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    # Delete connector (cascade will handle sync_jobs)
    db.execute(
        text("DELETE FROM connectors WHERE id = :connector_id"),
        {"connector_id": connector_id}
    )
    db.commit()
    
    return {"message": "Connector deleted successfully"}


@router.post("/{connector_id}/test", response_model=ConnectorTestResponse)
async def test_connector(
    domain_id: str,
    connector_id: str,
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Test connector connection"""
    # Get user's organization
    org_result = connector_service.db.execute(
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
    
    try:
        result = await connector_service.test_connector_connection(connector_id, organization_id)
        
        return ConnectorTestResponse(
            success=result["success"],
            connection_details=result.get("connection_details"),
            error_details=result.get("error_details"),
            requires_reauth=result.get("requires_reauth", False),
            tested_at=datetime.utcnow()
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Connection test failed: {str(e)}")


@router.post("/{connector_id}/sync")
async def sync_connector(
    domain_id: str,
    connector_id: str,
    background_tasks: BackgroundTasks,
    full_sync: bool = Query(False, description="Perform full sync instead of incremental"),
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Trigger connector synchronization"""
    # Get user's organization
    org_result = connector_service.db.execute(
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
    
    try:
        # Start sync in background
        result = await connector_service.sync_connector(connector_id, organization_id, full_sync)
        
        return {
            "message": "Sync initiated successfully",
            "sync_job_id": result["sync_job_id"],
            "full_sync": full_sync
        }
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {str(e)}")


@router.get("/{connector_id}/stats", response_model=ConnectorStatsResponse)
async def get_connector_stats(
    domain_id: str,
    connector_id: str,
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get connector statistics"""
    # Get user's organization
    org_result = connector_service.db.execute(
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
    
    try:
        stats = await connector_service.get_connector_stats(connector_id, organization_id)
        
        return ConnectorStatsResponse(**stats)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.get("/{connector_id}/sync-jobs", response_model=List[SyncJobResponse])
async def get_sync_jobs(
    domain_id: str,
    connector_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[SyncStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get sync jobs for a connector"""
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
    
    # Build query
    where_conditions = [
        "sj.connector_id = :connector_id",
        "sj.organization_id = :org_id"
    ]
    params = {
        "connector_id": connector_id,
        "org_id": organization_id,
        "skip": skip,
        "limit": limit
    }
    
    if status:
        where_conditions.append("sj.status = :status")
        params["status"] = status.value
    
    where_clause = " AND ".join(where_conditions)
    
    sync_jobs = db.execute(
        text(f"""
            SELECT sj.* FROM sync_jobs sj
            WHERE {where_clause}
            ORDER BY sj.created_at DESC
            OFFSET :skip LIMIT :limit
        """),
        params
    ).fetchall()
    
    return [
        SyncJobResponse(
            id=str(job.id),
            connector_id=str(job.connector_id),
            status=SyncStatus(job.status),
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            error_message=job.error_message,
            metadata=job.metadata,
            created_at=job.created_at
        )
        for job in sync_jobs
    ]


@router.get("/{connector_id}/sync-jobs/{sync_job_id}", response_model=SyncJobResponse)
async def get_sync_job(
    domain_id: str,
    connector_id: str,
    sync_job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get a specific sync job by ID"""
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
    
    # Get specific sync job
    sync_job = db.execute(
        text("""
            SELECT sj.* FROM sync_jobs sj
            WHERE sj.id = :sync_job_id 
            AND sj.connector_id = :connector_id
            AND sj.organization_id = :org_id
        """),
        {
            "sync_job_id": sync_job_id,
            "connector_id": connector_id,
            "org_id": organization_id
        }
    ).fetchone()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return SyncJobResponse(
        id=str(sync_job.id),
        connector_id=str(sync_job.connector_id),
        organization_id=str(sync_job.organization_id),
        status=SyncStatus(sync_job.status),
        started_at=sync_job.started_at,
        completed_at=sync_job.completed_at,
        records_processed=sync_job.records_processed or 0,
        records_created=sync_job.records_created or 0,
        records_updated=sync_job.records_updated or 0,
        error_message=sync_job.error_message,
        metadata=sync_job.metadata,
        created_at=sync_job.created_at
    )


@router.websocket("/{connector_id}/sync-jobs/{sync_job_id}/status")
async def sync_job_status_websocket(
    websocket: WebSocket,
    domain_id: str,
    connector_id: str,
    sync_job_id: str,
    token: str = Query(..., description="JWT token for authentication")
):
    """WebSocket endpoint for real-time sync job status updates"""
    await websocket.accept()
    
    try:
        # TODO: Add proper authentication here
        # For now, we'll skip auth but in production you should validate the JWT token
        
        # Get database session
        from dependencies import get_db
        db = next(get_db())
        
        # Poll sync job status every 2 seconds
        while True:
            try:
                # Get current sync job status
                sync_job = db.execute(
                    text("""
                        SELECT sj.* FROM sync_jobs sj
                        WHERE sj.id = :sync_job_id 
                        AND sj.connector_id = :connector_id
                    """),
                    {
                        "sync_job_id": sync_job_id,
                        "connector_id": connector_id
                    }
                ).fetchone()
                
                if sync_job:
                    status_data = {
                        "id": str(sync_job.id),
                        "status": sync_job.status,
                        "started_at": sync_job.started_at.isoformat() if sync_job.started_at else None,
                        "completed_at": sync_job.completed_at.isoformat() if sync_job.completed_at else None,
                        "records_processed": sync_job.records_processed or 0,
                        "records_created": sync_job.records_created or 0,
                        "records_updated": sync_job.records_updated or 0,
                        "error_message": sync_job.error_message,
                        "metadata": sync_job.metadata
                    }
                    
                    await websocket.send_text(json.dumps(status_data))
                    
                    # If sync is completed or failed, close connection
                    if sync_job.status in ["completed", "failed"]:
                        await websocket.send_text(json.dumps({"message": "Sync job finished", "final_status": sync_job.status}))
                        break
                else:
                    await websocket.send_text(json.dumps({"error": "Sync job not found"}))
                    break
                
                # Wait 2 seconds before next poll
                await asyncio.sleep(2)
                
            except Exception as e:
                await websocket.send_text(json.dumps({"error": f"Error fetching status: {str(e)}"}))
                break
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for sync job {sync_job_id}")
    except Exception as e:
        print(f"WebSocket error for sync job {sync_job_id}: {e}")
    finally:
        db.close()


@router.get("/{connector_id}/sync-jobs", response_model=List[SyncJobResponse])
async def get_sync_jobs(
    domain_id: str,
    connector_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[SyncStatus] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get sync jobs for a connector"""
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
    
    # Build query
    where_conditions = [
        "sj.connector_id = :connector_id",
        "sj.organization_id = :org_id"
    ]
    params = {
        "connector_id": connector_id,
        "org_id": organization_id,
        "skip": skip,
        "limit": limit
    }
    
    if status:
        where_conditions.append("sj.status = :status")
        params["status"] = status.value
    
    where_clause = " AND ".join(where_conditions)
    
    sync_jobs = db.execute(
        text(f"""
            SELECT sj.* FROM sync_jobs sj
            WHERE {where_clause}
            ORDER BY sj.created_at DESC
            OFFSET :skip LIMIT :limit
        """),
        params
    ).fetchall()
    
    return [
        SyncJobResponse(
            id=str(job.id),
            connector_id=str(job.connector_id),
            status=SyncStatus(job.status),
            started_at=job.started_at,
            completed_at=job.completed_at,
            records_processed=job.records_processed,
            records_created=job.records_created,
            records_updated=job.records_updated,
            error_message=job.error_message,
            metadata=job.metadata,
            created_at=job.created_at
        )
        for job in sync_jobs
    ]


@router.get("/{connector_id}/sync-jobs/{sync_job_id}", response_model=SyncJobResponse)
async def get_sync_job(
    domain_id: str,
    connector_id: str,
    sync_job_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get a specific sync job by ID"""
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
    
    # Get specific sync job
    sync_job = db.execute(
        text("""
            SELECT sj.* FROM sync_jobs sj
            WHERE sj.id = :sync_job_id 
            AND sj.connector_id = :connector_id
            AND sj.organization_id = :org_id
        """),
        {
            "sync_job_id": sync_job_id,
            "connector_id": connector_id,
            "org_id": organization_id
        }
    ).fetchone()
    
    if not sync_job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return SyncJobResponse(
        id=str(sync_job.id),
        connector_id=str(sync_job.connector_id),
        organization_id=str(sync_job.organization_id),
        status=SyncStatus(sync_job.status),
        started_at=sync_job.started_at,
        completed_at=sync_job.completed_at,
        records_processed=sync_job.records_processed or 0,
        records_created=sync_job.records_created or 0,
        records_updated=sync_job.records_updated or 0,
        error_message=sync_job.error_message,
        metadata=sync_job.metadata,
        created_at=sync_job.created_at
    )


# OAuth Routes
@router.post("/oauth/initiate")
async def initiate_oauth(
    domain_id: str,
    oauth_request: OAuthInitiateRequest,
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Initiate OAuth flow for a connector"""
    # Get user's organization
    org_result = connector_service.db.execute(
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
    
    try:
        auth_url, state = await connector_service.oauth_service.initiate_oauth_flow(
            connector_type=oauth_request.connector_type,
            organization_id=organization_id,
            domain=domain_id,
            user_id=current_user["id"],
            redirect_uri=oauth_request.redirect_uri
        )
        
        return {
            "auth_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth initiation failed: {str(e)}")


@router.post("/oauth/callback")
async def oauth_callback(
    domain_id: str,
    callback_request: OAuthCallbackRequest,
    connector_service: ConnectorService = Depends(get_connector_service),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Handle OAuth callback and store tokens"""
    try:
        success, result = await connector_service.oauth_service.handle_oauth_callback(
            code=callback_request.code,
            state=callback_request.state,
            redirect_uri=callback_request.redirect_uri
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=result.get("error", "OAuth callback failed"))
        
        return {
            "success": True,
            "connector_type": result["connector_type"],
            "tokens": result["tokens"],
            "message": "OAuth authentication successful"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")


# ============================================================================
# WEB SCRAPER SPECIFIC ENDPOINTS
# ============================================================================

@router.post("/{connector_id}/preview", response_model=Dict[str, Any])
async def preview_web_scraper(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Preview what URLs would be crawled by the web scraper without actually crawling them"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create connector config
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=connector.domain_name,
            auth_config=connector.auth_config,
            sync_config=connector.sync_config,
            mapping_config=connector.mapping_config,
            is_enabled=connector.is_enabled
        )
        
        # Create connector instance and get preview
        scraper = WebScraperConnector(config)
        preview = await scraper.preview_crawl()
        
        return {
            "preview": {
                "discovered_urls": preview.discovered_urls,
                "allowed_urls": preview.allowed_urls,
                "blocked_urls": preview.blocked_urls,
                "robots_blocked": preview.robots_blocked,
                "external_urls": preview.external_urls,
                "estimated_pages": preview.estimated_pages,
                "estimated_duration": preview.estimated_duration
            },
            "summary": {
                "total_discovered": len(preview.discovered_urls),
                "total_allowed": len(preview.allowed_urls),
                "total_blocked": len(preview.blocked_urls),
                "robots_blocked": len(preview.robots_blocked),
                "external_urls": len(preview.external_urls)
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preview failed: {str(e)}")


@router.post("/{connector_id}/test-config", response_model=Dict[str, Any])
async def test_web_scraper_config(
    domain_id: str,
    connector_id: str,
    config_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Test web scraper configuration without saving"""
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
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create temporary connector config for testing
        config = ConnectorConfig(
            id="test",
            name="Test Configuration",
            connector_type="web_scraper",
            organization_id=organization_id,
            domain=domain_id,
            auth_config=config_data,
            sync_config={},
            mapping_config={},
            is_enabled=True
        )
        
        # Test the configuration
        scraper = WebScraperConnector(config)
        success, result = await scraper.test_connection()
        
        return {
            "success": success,
            "result": result,
            "configuration_valid": success
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Configuration test failed: {str(e)}")


@router.get("/{connector_id}/crawl-stats", response_model=Dict[str, Any])
async def get_web_scraper_stats(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get detailed crawl statistics for web scraper"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Get crawl statistics from database
        crawl_stats = db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_pages,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_crawls,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_crawls,
                    AVG(word_count) as avg_word_count,
                    SUM(word_count) as total_words,
                    MIN(last_crawled) as first_crawl,
                    MAX(last_crawled) as last_crawl
                FROM crawled_pages cp
                JOIN connectors c ON cp.domain_id = c.domain_id
                WHERE c.id = :connector_id AND cp.organization_id = :org_id
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        # Get recent sync jobs
        recent_syncs = db.execute(
            text("""
                SELECT * FROM sync_jobs 
                WHERE connector_id = :connector_id AND organization_id = :org_id
                ORDER BY created_at DESC 
                LIMIT 10
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchall()
        
        return {
            "crawl_stats": {
                "total_pages": crawl_stats.total_pages or 0,
                "successful_crawls": crawl_stats.successful_crawls or 0,
                "failed_crawls": crawl_stats.failed_crawls or 0,
                "success_rate": (crawl_stats.successful_crawls or 0) / max(crawl_stats.total_pages or 1, 1) * 100,
                "avg_word_count": float(crawl_stats.avg_word_count or 0),
                "total_words": crawl_stats.total_words or 0,
                "first_crawl": crawl_stats.first_crawl.isoformat() if crawl_stats.first_crawl else None,
                "last_crawl": crawl_stats.last_crawl.isoformat() if crawl_stats.last_crawl else None
            },
            "recent_syncs": [
                {
                    "id": str(sync.id),
                    "status": sync.status,
                    "started_at": sync.started_at.isoformat() if sync.started_at else None,
                    "completed_at": sync.completed_at.isoformat() if sync.completed_at else None,
                    "records_processed": sync.records_processed,
                    "error_message": sync.error_message
                }
                for sync in recent_syncs
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawl stats: {str(e)}")


@router.put("/{connector_id}/crawl-rules", response_model=Dict[str, Any])
async def update_crawl_rules(
    domain_id: str,
    connector_id: str,
    rules_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Update crawl rules for web scraper with validation"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Validate regex patterns
        include_patterns = rules_data.get('include_patterns', [])
        exclude_patterns = rules_data.get('exclude_patterns', [])
        
        for pattern in include_patterns + exclude_patterns:
            try:
                re.compile(pattern)
            except re.error as e:
                raise HTTPException(status_code=400, detail=f"Invalid regex pattern '{pattern}': {str(e)}")
        
        # Validate file size limit
        max_file_size = rules_data.get('max_file_size', 5 * 1024 * 1024)
        if max_file_size > 100 * 1024 * 1024:  # 100MB limit
            raise HTTPException(status_code=400, detail="Maximum file size cannot exceed 100MB")
        
        # Update connector auth_config with new rules
        current_auth_config = connector.auth_config or {}
        updated_auth_config = {
            **current_auth_config,
            'include_patterns': include_patterns,
            'exclude_patterns': exclude_patterns,
            'follow_external': rules_data.get('follow_external', False),
            'respect_robots': rules_data.get('respect_robots', True),
            'max_file_size': max_file_size,
            'custom_user_agent': rules_data.get('custom_user_agent', 'CortexQ-Bot/1.0'),
            'crawl_frequency_hours': rules_data.get('crawl_frequency_hours', 24),
            'content_filters': rules_data.get('content_filters', {
                'min_word_count': 10,
                'exclude_nav_elements': True,
                'exclude_footer_elements': True,
                'extract_metadata': True
            })
        }
        
        # Update database
        db.execute(
            text("""
                UPDATE connectors 
                SET auth_config = :auth_config, updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {
                "auth_config": json.dumps(updated_auth_config),
                "connector_id": connector_id,
                "org_id": organization_id
            }
        )
        db.commit()
        
        # Log the change
        AuditLogger.log_event(
            db, "connector_config_update", current_user["id"], "connectors", "update",
            f"Updated crawl rules for connector {connector.name}",
            {"connector_id": connector_id, "rules_updated": list(rules_data.keys())}
        )
        
        return {
            "success": True,
            "message": "Crawl rules updated successfully",
            "updated_rules": {
                "include_patterns": include_patterns,
                "exclude_patterns": exclude_patterns,
                "follow_external": rules_data.get('follow_external', False),
                "respect_robots": rules_data.get('respect_robots', True),
                "max_file_size": max_file_size,
                "custom_user_agent": updated_auth_config.get('custom_user_agent'),
                "crawl_frequency_hours": updated_auth_config.get('crawl_frequency_hours')
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update crawl rules: {str(e)}")


@router.get("/{connector_id}/crawled-pages", response_model=Dict[str, Any])
async def get_crawled_pages(
    domain_id: str,
    connector_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status_filter: Optional[str] = Query(None, regex="^(success|failed|skipped)$"),
    search_query: Optional[str] = Query(None, min_length=1, max_length=255),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get paginated list of crawled pages with filtering and search"""
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
    
    try:
        # Build dynamic query - need to join with connectors to match connector_id to domain_id
        where_conditions = ["c.id = :connector_id", "cp.organization_id = :org_id"]
        query_params = {
            "connector_id": connector_id,
            "org_id": organization_id,
            "offset": (page - 1) * page_size,
            "limit": page_size
        }
        
        if status_filter:
            where_conditions.append("cp.status = :status_filter")
            query_params["status_filter"] = status_filter
        
        if search_query:
            where_conditions.append("(cp.title ILIKE :search OR cp.url ILIKE :search OR cp.content ILIKE :search)")
            query_params["search"] = f"%{search_query}%"
        
        where_clause = " AND ".join(where_conditions)
        
        # Get total count
        total_count = db.execute(
            text(f"""
                SELECT COUNT(*) as count
                FROM crawled_pages cp
                JOIN connectors c ON cp.domain_id = c.domain_id
                WHERE {where_clause}
            """),
            query_params
        ).fetchone().count
        
        # Get pages
        pages = db.execute(
            text(f"""
                SELECT 
                    cp.id, cp.url, cp.title, cp.status, cp.word_count, cp.content_hash,
                    cp.last_crawled, cp.depth, cp.content_type, cp.file_size, cp.error_message,
                    CASE 
                        WHEN LENGTH(cp.content) > 200 THEN SUBSTRING(cp.content FROM 1 FOR 200) || '...'
                        ELSE cp.content
                    END as content_preview
                FROM crawled_pages cp
                JOIN connectors c ON cp.domain_id = c.domain_id
                WHERE {where_clause}
                ORDER BY cp.last_crawled DESC
                OFFSET :offset LIMIT :limit
            """),
            query_params
        ).fetchall()
        
        pages_data = [
            {
                "id": str(page.id),
                "url": page.url,
                "title": page.title,
                "status": page.status,
                "word_count": page.word_count,
                "content_hash": page.content_hash,
                "last_crawled": page.last_crawled.isoformat() if page.last_crawled else None,
                "depth": page.depth,
                "content_type": page.content_type,
                "file_size": page.file_size,
                "error_message": page.error_message,
                "content_preview": page.content_preview
            }
            for page in pages
        ]
        
        return {
            "pages": pages_data,
            "pagination": {
                "current_page": page,
                "page_size": page_size,
                "total_pages": (total_count + page_size - 1) // page_size,
                "total_count": total_count,
                "has_next": page * page_size < total_count,
                "has_previous": page > 1
            },
            "filters": {
                "status_filter": status_filter,
                "search_query": search_query
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve crawled pages: {str(e)}")


@router.delete("/{connector_id}/crawled-pages/{page_id}")
async def delete_crawled_page(
    domain_id: str,
    connector_id: str,
    page_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Delete a specific crawled page"""
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
    
    try:
        # Check if page exists and belongs to user's organization
        page = db.execute(
            text("""
                SELECT cp.url FROM crawled_pages cp
                JOIN connectors c ON cp.domain_id = c.domain_id
                WHERE cp.id = :page_id AND c.id = :connector_id AND cp.organization_id = :org_id
            """),
            {
                "page_id": page_id,
                "connector_id": connector_id,
                "org_id": organization_id
            }
        ).fetchone()
        
        if not page:
            raise HTTPException(status_code=404, detail="Crawled page not found")
        
        # Delete the page
        db.execute(
            text("""
                DELETE FROM crawled_pages 
                WHERE id = :page_id AND domain_id = (
                    SELECT domain_id FROM connectors WHERE id = :connector_id
                ) AND organization_id = :org_id
            """),
            {
                "page_id": page_id,
                "connector_id": connector_id,
                "org_id": organization_id
            }
        )
        db.commit()
        
        # Log the deletion
        AuditLogger.log_event(
            db, "crawled_page_delete", current_user["id"], "crawled_pages", "delete",
            f"Deleted crawled page: {page.url}",
            {"page_id": page_id, "connector_id": connector_id}
        )
        
        return {"success": True, "message": "Crawled page deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete crawled page: {str(e)}")


@router.post("/{connector_id}/schedule-crawl", response_model=Dict[str, Any])
async def schedule_web_scraper_crawl(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Schedule a crawl for web scraper connector"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Import and create connector instance
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        config = ConnectorConfig(
            id=connector.id,
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=connector.auth_config or {},
            sync_config=connector.sync_config or {},
            mapping_config=connector.mapping_config or {},
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        result = await scraper.schedule_crawl(db, connector_id, organization_id, domain_name)
        
        # Log the scheduling action
        AuditLogger.log_event(
            db, "web_scraper_schedule", current_user["id"], "connectors", "schedule",
            f"Scheduled crawl for connector {connector.name}",
            {"connector_id": connector_id, "result": result}
        )
        
        return {
            "success": True,
            "message": "Crawl scheduling processed",
            **result
        }
        
    except Exception as e:
        logger.error(f"Error scheduling crawl: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to schedule crawl: {str(e)}")


@router.get("/{connector_id}/performance-metrics", response_model=Dict[str, Any])
async def get_web_scraper_performance_metrics(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get performance metrics for web scraper connector"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Import and create connector instance
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=connector.auth_config or {},
            sync_config=connector.sync_config or {},
            mapping_config=connector.mapping_config or {},
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        metrics = await scraper.get_performance_metrics(db, connector_id, organization_id)
        
        return {
            "success": True,
            "message": "Performance metrics retrieved successfully",
            "metrics": {
                "pages_per_second": metrics.pages_per_second,
                "avg_response_time": metrics.avg_response_time,
                "error_rate": metrics.error_rate,
                "bandwidth_usage_mb": metrics.bandwidth_usage_mb,
                "cache_hit_rate": metrics.cache_hit_rate,
                "robots_compliance_rate": metrics.robots_compliance_rate
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get performance metrics: {str(e)}")


@router.get("/{connector_id}/optimization-suggestions", response_model=Dict[str, Any])
async def get_web_scraper_optimization_suggestions(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get optimization suggestions for web scraper connector"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Import and create connector instance
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=connector.auth_config or {},
            sync_config=connector.sync_config or {},
            mapping_config=connector.mapping_config or {},
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        optimization_data = await scraper.optimize_crawl_settings(db, connector_id, organization_id)
        
        return {
            "success": True,
            "optimization": optimization_data,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get optimization suggestions: {str(e)}")


@router.post("/{connector_id}/apply-optimization", response_model=Dict[str, Any])
async def apply_web_scraper_optimization(
    domain_id: str,
    connector_id: str,
    optimization_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Apply optimization suggestions to web scraper connector"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Get current auth config
        current_auth_config = connector.auth_config or {}
        
        # Apply recommended settings
        recommended_settings = optimization_data.get('recommended_settings', {})
        
        # Update auth config with new settings
        for key, value in recommended_settings.items():
            current_auth_config[key] = value
        
        # Update connector in database
        db.execute(
            text("""
                UPDATE connectors 
                SET auth_config = :auth_config, updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {
                "auth_config": json.dumps(current_auth_config),
                "connector_id": connector_id,
                "org_id": organization_id
            }
        )
        
        db.commit()
        
        # Log the optimization action
        AuditLogger.log_event(
            db, "web_scraper_optimize", current_user["id"], "connectors", "update",
            f"Applied optimization to connector {connector.name}",
            {"connector_id": connector_id, "applied_settings": recommended_settings}
        )
        
        return {
            "success": True,
            "message": "Optimization settings applied successfully",
            "applied_settings": recommended_settings
        }
        
    except Exception as e:
        logger.error(f"Error applying optimization: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply optimization: {str(e)}")


@router.get("/{connector_id}/content-analytics", response_model=Dict[str, Any])
async def get_web_scraper_content_analytics(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get comprehensive content analytics for web scraper"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create connector config
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=connector.domain_name,
            auth_config=connector.auth_config,
            sync_config=connector.sync_config,
            mapping_config=connector.mapping_config,
            is_enabled=connector.is_enabled
        )
        
        # Create connector instance and get analytics
        scraper = WebScraperConnector(config)
        analytics = await scraper.get_content_analytics()
        
        return {
            "analytics": analytics,
            "generated_at": datetime.utcnow().isoformat(),
            "connector_id": connector_id
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get content analytics: {str(e)}")


@router.get("/{connector_id}/crawl-session-status", response_model=Dict[str, Any])
async def get_crawl_session_status(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get real-time crawl session status"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create connector config
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=connector.domain_name,
            auth_config=connector.auth_config,
            sync_config=connector.sync_config,
            mapping_config=connector.mapping_config,
            is_enabled=connector.is_enabled
        )
        
        # Create connector instance and get session status
        scraper = WebScraperConnector(config)
        session_status = await scraper.get_crawl_session_status()
        
        if session_status:
            return {
                "session": session_status,
                "status": "active"
            }
        else:
            return {
                "session": None,
                "status": "inactive",
                "message": "No active crawl session"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session status: {str(e)}")


@router.post("/{connector_id}/intelligent-crawl", response_model=Dict[str, Any])
async def start_intelligent_crawl(
    domain_id: str,
    connector_id: str,
    background_tasks: BackgroundTasks,
    crawl_options: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Start an intelligent crawl with enhanced features"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*, od.domain_name as domain_name
            FROM connectors c
            JOIN organization_domains od ON c.domain_id = od.id
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Merge crawl options with existing config
        auth_config = connector.auth_config.copy() if connector.auth_config else {}
        if crawl_options:
            auth_config.update(crawl_options)
            # Enable intelligent features
            auth_config['intelligent_discovery'] = crawl_options.get('intelligent_discovery', True)
            auth_config['real_time_monitoring'] = crawl_options.get('real_time_monitoring', True)
            auth_config['quality_threshold'] = crawl_options.get('quality_threshold', 0.3)
            auth_config['duplicate_threshold'] = crawl_options.get('duplicate_threshold', 0.85)
        
        # Create connector config
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=connector.domain_name,
            auth_config=auth_config,
            sync_config=connector.sync_config,
            mapping_config=connector.mapping_config,
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        
        # Log the crawl initiation
        AuditLogger.log_event(
            db, "intelligent_crawl_started", current_user["id"], "connectors", "crawl",
            f"Intelligent crawl started for connector {connector.name}",
            {"connector_id": connector_id, "organization_id": organization_id}
        )
        
        # Start background crawl
        def run_intelligent_crawl():
            import asyncio
            
            async def crawl_task():
                scraper = WebScraperConnector(config)
                results = await scraper.crawl_with_intelligence(
                    db=db,
                    connector_id=connector_id,
                    organization_id=organization_id,
                    domain=connector.domain_name
                )
                return results
            
            return asyncio.run(crawl_task())
        
        background_tasks.add_task(run_intelligent_crawl)
        
        return {
            "status": "started",
            "message": "Intelligent crawl started successfully",
            "connector_id": connector_id,
            "features_enabled": {
                "intelligent_discovery": auth_config.get('intelligent_discovery', True),
                "real_time_monitoring": auth_config.get('real_time_monitoring', True),
                "quality_filtering": auth_config.get('quality_threshold', 0.3) > 0,
                "duplicate_detection": auth_config.get('duplicate_threshold', 0.85) < 1.0
            },
            "estimated_start_time": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error starting intelligent crawl: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start intelligent crawl: {str(e)}")


@router.get("/{connector_id}/content-quality-report", response_model=Dict[str, Any])
async def get_content_quality_report(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get detailed content quality report"""
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
    
    try:
        # Get quality metrics from database
        quality_report = db.execute(
            text("""
                SELECT 
                    cp.url,
                    cp.title,
                    cp.word_count,
                    cp.quality_score,
                    cp.status,
                    cp.last_crawled,
                    cp.metadata
                FROM crawled_pages cp
                WHERE cp.connector_id = :connector_id 
                AND cp.organization_id = :org_id
                AND cp.status = 'success'
                ORDER BY cp.quality_score DESC
                LIMIT 100
            """),
            {
                "connector_id": connector_id,
                "org_id": organization_id
            }
        ).fetchall()
        
        if not quality_report:
            return {
                "report": {
                    "total_pages": 0,
                    "quality_distribution": {},
                    "recommendations": []
                },
                "pages": []
            }
        
        # Analyze quality distribution
        quality_scores = [float(page.quality_score) for page in quality_report if page.quality_score]
        
        quality_distribution = {
            "excellent": len([s for s in quality_scores if s >= 0.8]),
            "good": len([s for s in quality_scores if 0.6 <= s < 0.8]),
            "fair": len([s for s in quality_scores if 0.4 <= s < 0.6]),
            "poor": len([s for s in quality_scores if s < 0.4])
        }
        
        # Generate recommendations
        recommendations = []
        if quality_distribution["poor"] > len(quality_scores) * 0.3:
            recommendations.append({
                "type": "quality_improvement",
                "message": "High number of poor quality pages detected. Consider adjusting content filters.",
                "action": "Review and improve content selection criteria"
            })
        
        if quality_distribution["excellent"] == 0:
            recommendations.append({
                "type": "content_discovery",
                "message": "No excellent content found. Consider expanding crawl scope.",
                "action": "Review URL patterns and increase crawl depth"
            })
        
        # Top performing pages
        top_pages = []
        for page in quality_report[:10]:  # Top 10
            page_data = {
                "url": page.url,
                "title": page.title or "No title",
                "quality_score": float(page.quality_score) if page.quality_score else 0,
                "word_count": page.word_count,
                "last_crawled": page.last_crawled.isoformat() if page.last_crawled else None
            }
            
            # Extract quality metrics from metadata if available
            if page.metadata and isinstance(page.metadata, dict):
                quality_metrics = page.metadata.get('quality_metrics', {})
                if quality_metrics:
                    page_data['detailed_metrics'] = {
                        "readability_score": quality_metrics.get('readability_score', 0),
                        "content_density": quality_metrics.get('content_density', 0),
                        "semantic_richness": quality_metrics.get('semantic_richness', 0),
                        "information_density": quality_metrics.get('information_density', 0)
                    }
            
            top_pages.append(page_data)
        
        return {
            "report": {
                "total_pages": len(quality_report),
                "average_quality_score": sum(quality_scores) / len(quality_scores) if quality_scores else 0,
                "quality_distribution": quality_distribution,
                "recommendations": recommendations,
                "analysis_date": datetime.utcnow().isoformat()
            },
            "top_pages": top_pages
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate quality report: {str(e)}")


@router.put("/{connector_id}/enhanced-config", response_model=Dict[str, Any])
async def update_enhanced_web_scraper_config(
    domain_id: str,
    connector_id: str,
    enhanced_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Update web scraper with enhanced configuration options"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT c.*
            FROM connectors c
            WHERE c.id = :connector_id AND c.organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Validate enhanced configuration
        valid_enhanced_keys = {
            'intelligent_discovery', 'real_time_monitoring', 'adaptive_scheduling',
            'quality_threshold', 'duplicate_threshold', 'max_file_size',
            'content_filters', 'crawl_frequency_hours', 'custom_user_agent'
        }
        
        # Filter out invalid keys
        filtered_config = {k: v for k, v in enhanced_config.items() if k in valid_enhanced_keys}
        
        # Merge with existing auth config
        current_auth_config = connector.auth_config or {}
        updated_auth_config = {**current_auth_config, **filtered_config}
        
        # Update connector in database
        db.execute(
            text("""
                UPDATE connectors 
                SET auth_config = :auth_config,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {
                "auth_config": json.dumps(updated_auth_config),
                "connector_id": connector_id,
                "org_id": organization_id
            }
        )
        db.commit()
        
        return {
            "status": "updated",
            "message": "Enhanced configuration applied successfully",
            "updated_config": filtered_config,
            "features_enabled": {
                "intelligent_discovery": updated_auth_config.get('intelligent_discovery', True),
                "real_time_monitoring": updated_auth_config.get('real_time_monitoring', True),
                "adaptive_scheduling": updated_auth_config.get('adaptive_scheduling', True),
                "quality_filtering": updated_auth_config.get('quality_threshold', 0.3) > 0,
                "duplicate_detection": updated_auth_config.get('duplicate_threshold', 0.85) < 1.0
            }
        }
        
    except Exception as e:
        logger.error(f"Error applying enhanced configuration: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply configuration: {str(e)}")


@router.get("/{connector_id}/duplicate-analysis", response_model=Dict[str, Any])
async def get_duplicate_content_analysis(
    domain_id: str,
    connector_id: str,
    threshold: float = Query(0.8, ge=0.0, le=1.0, description="Similarity threshold for duplicates"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get duplicate content analysis for web scraper"""
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
    
    try:
        # Get pages with content hashes
        pages = db.execute(
            text("""
                SELECT 
                    cp.id,
                    cp.url,
                    cp.title,
                    cp.content_hash,
                    cp.word_count,
                    cp.last_crawled,
                    cp.metadata
                FROM crawled_pages cp
                WHERE cp.connector_id = :connector_id 
                AND cp.organization_id = :org_id
                AND cp.status = 'success'
                AND cp.content_hash IS NOT NULL
                ORDER BY cp.last_crawled DESC
                LIMIT 500
            """),
            {
                "connector_id": connector_id,
                "org_id": organization_id
            }
        ).fetchall()
        
        if not pages:
            return {
                "analysis": {
                    "total_pages": 0,
                    "unique_pages": 0,
                    "duplicate_groups": [],
                    "duplication_rate": 0.0
                }
            }
        
        # Group by content hash for exact duplicates
        hash_groups = {}
        for page in pages:
            content_hash = page.content_hash
            if content_hash not in hash_groups:
                hash_groups[content_hash] = []
            hash_groups[content_hash].append({
                "id": str(page.id),
                "url": page.url,
                "title": page.title or "No title",
                "word_count": page.word_count,
                "last_crawled": page.last_crawled.isoformat() if page.last_crawled else None
            })
        
        # Find duplicate groups (more than one page with same hash)
        duplicate_groups = []
        exact_duplicates = 0
        
        for content_hash, group_pages in hash_groups.items():
            if len(group_pages) > 1:
                duplicate_groups.append({
                    "content_hash": content_hash,
                    "duplicate_count": len(group_pages),
                    "pages": group_pages,
                    "similarity_type": "exact"
                })
                exact_duplicates += len(group_pages) - 1  # All but one are duplicates
        
        # Calculate near-duplicates using quality metrics if available
        near_duplicate_groups = []
        for page in pages:
            if page.metadata and isinstance(page.metadata, dict):
                quality_metrics = page.metadata.get('quality_metrics', {})
                similarity = quality_metrics.get('duplicate_similarity', 0)
                if similarity >= threshold and similarity < 1.0:
                    # This is a near-duplicate
                    # For simplicity, we'll mark it but not group it properly
                    # Full similarity analysis would require more complex processing
                    pass
        
        unique_pages = len(hash_groups)
        total_pages = len(pages)
        duplication_rate = exact_duplicates / total_pages if total_pages > 0 else 0
        
        return {
            "analysis": {
                "total_pages": total_pages,
                "unique_pages": unique_pages,
                "exact_duplicates": exact_duplicates,
                "duplicate_groups": duplicate_groups[:20],  # Limit for response size
                "duplication_rate": round(duplication_rate, 3),
                "threshold_used": threshold,
                "analysis_date": datetime.utcnow().isoformat()
            },
            "recommendations": [
                {
                    "type": "deduplication",
                    "message": f"Found {exact_duplicates} exact duplicate pages",
                    "action": "Consider removing duplicate URLs from crawl scope"
                } if exact_duplicates > 0 else None,
                {
                    "type": "url_patterns",
                    "message": "Review URL patterns to avoid duplicate content",
                    "action": "Add exclude patterns for known duplicate paths"
                } if duplication_rate > 0.2 else None
            ]
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to analyze duplicates: {str(e)}")


@router.post("/{connector_id}/advanced-crawl", response_model=Dict[str, Any])
async def start_advanced_crawl(
    domain_id: str,
    connector_id: str,
    background_tasks: BackgroundTasks,
    crawl_options: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Start advanced crawl with enhanced pipeline and smart queue management"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        # Create connector config with enhanced options
        enhanced_config = connector.auth_config.copy()
        if crawl_options:
            enhanced_config.update(crawl_options)
        
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=enhanced_config,
            sync_config=connector.sync_config,
            mapping_config=connector.mapping_config,
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        
        # Log the crawl initiation
        AuditLogger.log_event(
            db, "advanced_crawl_started", current_user["id"], "connectors", "crawl",
            f"Advanced crawl started for connector {connector.name}",
            {"connector_id": connector_id, "organization_id": organization_id}
        )
        
        # Start background crawl
        def run_advanced_crawl():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def crawl_task():
                try:
                    results = await scraper.crawl_with_advanced_pipeline(
                        db=db, 
                        connector_id=connector_id, 
                        organization_id=organization_id,
                        domain=domain_name
                    )
                    
                    # Update connector last sync
                    db.execute(
                        text("""
                            UPDATE connectors 
                            SET last_sync_at = NOW(), 
                                sync_status = 'completed'
                            WHERE id = :connector_id
                        """),
                        {"connector_id": connector_id}
                    )
                    db.commit()
                    
                    logger.info(f"Advanced crawl completed for connector {connector_id}: {len(results)} pages processed")
                    
                except Exception as e:
                    logger.error(f"Advanced crawl failed for connector {connector_id}: {e}")
                    
                    # Update connector sync status
                    db.execute(
                        text("""
                            UPDATE connectors 
                            SET sync_status = 'failed'
                            WHERE id = :connector_id
                        """),
                        {"connector_id": connector_id}
                    )
                    db.commit()
            
            loop.run_until_complete(crawl_task())
            loop.close()
        
        background_tasks.add_task(run_advanced_crawl)
        
        return {
            "success": True,
            "message": "Advanced crawl started successfully",
            "crawler_features": {
                "advanced_pipeline": scraper.enable_advanced_pipeline,
                "smart_retry": scraper.enable_smart_retry,
                "queue_management": scraper.enable_url_queue_management,
                "extractors": scraper.content_pipeline.extractors,
                "filters": scraper.content_pipeline.filters,
                "enrichers": scraper.content_pipeline.enrichers
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting advanced crawl: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start advanced crawl: {str(e)}")


@router.get("/{connector_id}/advanced-analytics", response_model=Dict[str, Any])
async def get_advanced_crawler_analytics(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get advanced analytics from the web scraper"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=connector.auth_config or {},
            sync_config=connector.sync_config or {},
            mapping_config=connector.mapping_config or {},
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        analytics = await scraper.get_advanced_crawler_analytics(db, connector_id, organization_id)
        
        return {
            "success": True,
            "analytics": analytics,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting advanced analytics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get advanced analytics: {str(e)}")


@router.get("/{connector_id}/crawler-optimization", response_model=Dict[str, Any])
async def get_crawler_optimization_suggestions(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get optimization suggestions for the web scraper"""
    # Get user's organization
    org_result = db.execute(
        text("""
            SELECT om.organization_id, od.domain_name
            FROM organization_members om
            JOIN organization_domains od ON om.organization_id = od.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND od.id = :domain_id
            LIMIT 1
        """),
        {"user_id": current_user["id"], "domain_id": domain_id}
    ).fetchone()
    
    if not org_result:
        raise HTTPException(status_code=403, detail="User not associated with this domain")
    
    organization_id = str(org_result.organization_id)
    domain_name = org_result.domain_name
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        from connectors.web_scraper_connector import WebScraperConnector
        from services.base_connector import ConnectorConfig
        
        config = ConnectorConfig(
            id=str(connector.id),
            name=connector.name,
            connector_type=connector.connector_type,
            organization_id=organization_id,
            domain=domain_name,
            auth_config=connector.auth_config or {},
            sync_config=connector.sync_config or {},
            mapping_config=connector.mapping_config or {},
            is_enabled=connector.is_enabled
        )
        
        scraper = WebScraperConnector(config)
        optimization_data = await scraper.optimize_crawler_settings(db, connector_id, organization_id)
        
        return {
            "success": True,
            "optimization": optimization_data,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting optimization suggestions: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get optimization suggestions: {str(e)}")


@router.put("/{connector_id}/apply-advanced-config", response_model=Dict[str, Any])
async def apply_advanced_configuration(
    domain_id: str,
    connector_id: str,
    advanced_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Apply advanced configuration settings to web scraper"""
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
    
    # Get connector
    connector = db.execute(
        text("""
            SELECT * FROM connectors 
            WHERE id = :connector_id AND organization_id = :org_id
        """),
        {"connector_id": connector_id, "org_id": organization_id}
    ).fetchone()
    
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    
    if connector.connector_type != "web_scraper":
        raise HTTPException(status_code=400, detail="This endpoint is only for web scraper connectors")
    
    try:
        # Validate advanced configuration
        valid_keys = {
            'enable_advanced_pipeline', 'enable_smart_retry', 'enable_url_queue_management',
            'content_pipeline', 'quality_threshold', 'allowed_languages',
            'content_filters', 'retry_settings', 'queue_settings'
        }
        
        # Filter out invalid keys
        filtered_config = {k: v for k, v in advanced_config.items() if k in valid_keys}
        
        # Merge with existing auth config
        current_auth_config = connector.auth_config or {}
        updated_auth_config = {**current_auth_config, **filtered_config}
        
        # Update connector
        db.execute(
            text("""
                UPDATE connectors 
                SET auth_config = :auth_config,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {
                "auth_config": json.dumps(updated_auth_config),
                "connector_id": connector_id,
                "org_id": organization_id
            }
        )
        
        db.commit()
        
        # Log the configuration update
        AuditLogger.log_event(
            db, "advanced_config_updated", current_user["id"], "connectors", "update",
            f"Advanced configuration updated for connector {connector.name}",
            {"connector_id": connector_id, "updated_config": filtered_config}
        )
        
        return {
            "success": True,
            "message": "Advanced configuration applied successfully",
            "updated_config": filtered_config,
            "connector_id": connector_id
        }
        
    except Exception as e:
        logger.error(f"Error applying advanced configuration: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to apply configuration: {str(e)}")


@router.get("/{connector_id}/pipeline-status", response_model=Dict[str, Any])
async def get_content_pipeline_status(
    domain_id: str,
    connector_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get status of the content extraction pipeline"""
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
    
    try:
        # Get pipeline processing statistics
        pipeline_stats = db.execute(
            text("""
                SELECT 
                    COUNT(*) as total_pages,
                    COUNT(CASE WHEN metadata ? 'quality_score' THEN 1 END) as pages_with_quality,
                    COUNT(CASE WHEN metadata ? 'extracted_keywords' THEN 1 END) as pages_with_keywords,
                    COUNT(CASE WHEN metadata ? 'topic_categories' THEN 1 END) as pages_with_topics,
                    COUNT(CASE WHEN metadata ? 'sentiment_analysis' THEN 1 END) as pages_with_sentiment,
                    COUNT(CASE WHEN metadata ? 'readability_metrics' THEN 1 END) as pages_with_readability,
                    COUNT(CASE WHEN metadata ? 'images' THEN 1 END) as pages_with_images,
                    COUNT(CASE WHEN metadata ? 'tables' THEN 1 END) as pages_with_tables,
                    COUNT(CASE WHEN metadata ? 'forms' THEN 1 END) as pages_with_forms,
                    AVG(CASE WHEN metadata ? 'quality_score' THEN (metadata->>'quality_score')::float ELSE NULL END) as avg_quality,
                    COUNT(CASE WHEN status = 'filtered' THEN 1 END) as filtered_pages,
                    COUNT(CASE WHEN status = 'success' THEN 1 END) as successful_pages,
                    COUNT(CASE WHEN status = 'failed' THEN 1 END) as failed_pages
                FROM crawled_pages 
                WHERE connector_id = :connector_id AND organization_id = :org_id
                AND crawled_at > NOW() - INTERVAL '24 hours'
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        if not pipeline_stats:
            return {
                "success": True,
                "pipeline_status": "no_data",
                "message": "No recent crawl data found"
            }
        
        total_pages = pipeline_stats.total_pages or 0
        
        if total_pages == 0:
            return {
                "success": True,
                "pipeline_status": "no_data",
                "message": "No pages processed in the last 24 hours"
            }
        
        # Calculate pipeline effectiveness
        effectiveness = {
            "quality_analysis": (pipeline_stats.pages_with_quality or 0) / total_pages,
            "keyword_extraction": (pipeline_stats.pages_with_keywords or 0) / total_pages,
            "topic_categorization": (pipeline_stats.pages_with_topics or 0) / total_pages,
            "sentiment_analysis": (pipeline_stats.pages_with_sentiment or 0) / total_pages,
            "readability_analysis": (pipeline_stats.pages_with_readability or 0) / total_pages,
            "image_extraction": (pipeline_stats.pages_with_images or 0) / total_pages,
            "table_extraction": (pipeline_stats.pages_with_tables or 0) / total_pages,
            "form_extraction": (pipeline_stats.pages_with_forms or 0) / total_pages
        }
        
        # Determine overall pipeline health
        avg_effectiveness = sum(effectiveness.values()) / len(effectiveness)
        
        if avg_effectiveness > 0.8:
            pipeline_health = "excellent"
        elif avg_effectiveness > 0.6:
            pipeline_health = "good"
        elif avg_effectiveness > 0.4:
            pipeline_health = "fair"
        else:
            pipeline_health = "poor"
        
        return {
            "success": True,
            "pipeline_status": pipeline_health,
            "statistics": {
                "total_pages_processed": total_pages,
                "successful_pages": pipeline_stats.successful_pages or 0,
                "failed_pages": pipeline_stats.failed_pages or 0,
                "filtered_pages": pipeline_stats.filtered_pages or 0,
                "average_quality_score": float(pipeline_stats.avg_quality or 0),
                "success_rate": (pipeline_stats.successful_pages or 0) / max(1, total_pages)
            },
            "pipeline_effectiveness": effectiveness,
            "overall_effectiveness": avg_effectiveness,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting pipeline status: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get pipeline status: {str(e)}")


@router.post("/{connector_id}/ai-content-discovery", response_model=Dict[str, Any])
async def discover_trending_content(
    domain_id: str,
    connector_id: str,
    discovery_options: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """AI-powered trending content discovery and curation"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Get connector and domain info
        connector = db.execute(
            text("""
                SELECT c.*, od.domain_name as domain_name
                FROM connectors c
                JOIN organization_domains od ON c.domain_id = od.id
                WHERE c.id = :connector_id AND c.organization_id = :org_id
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        # Initialize AI content curator
        from connectors.web_scraper_connector import AIContentCurator
        ai_curator = AIContentCurator()
        
        # Discover trending content
        trending_content = await ai_curator.discover_trending_content(
            db, organization_id, connector.domain_name
        )
        
        # Auto-discover related content for top trending items
        related_discoveries = []
        for item in trending_content[:5]:  # Top 5 items
            related_urls = await ai_curator.auto_discover_related_content(
                db, item['url'], organization_id
            )
            if related_urls:
                related_discoveries.append({
                    'seed_url': item['url'],
                    'related_urls': related_urls,
                    'discovery_count': len(related_urls)
                })
        
        # Log audit event
        AuditLogger.log_event(
            db, "ai_content_discovery", current_user["id"], "connectors", "read",
            f"AI content discovery for connector {connector_id}",
            {"connector_id": connector_id, "discoveries_count": len(trending_content)}
        )
        
        return {
            "status": "success",
            "trending_content": trending_content,
            "related_discoveries": related_discoveries,
            "discovery_summary": {
                "total_trending_items": len(trending_content),
                "total_related_items": sum(len(rd['related_urls']) for rd in related_discoveries),
                "discovery_timestamp": datetime.utcnow().isoformat()
            },
            "ai_recommendations": [
                "Monitor top trending content for regular updates",
                "Consider prioritizing high-trend-score URLs in next crawl",
                "Review related content for potential new crawl targets"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in AI content discovery: {e}")
        raise HTTPException(status_code=500, detail=f"AI discovery error: {str(e)}")


@router.post("/{connector_id}/visual-content-analysis", response_model=Dict[str, Any])
async def analyze_visual_content(
    domain_id: str,
    connector_id: str,
    analysis_config: Dict[str, Any] = None,
    sample_urls: List[str] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Advanced visual content analysis for crawled pages"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Get sample URLs for analysis if not provided
        if not sample_urls:
            sample_result = db.execute(
                text("""
                    SELECT url FROM crawled_pages 
                    WHERE organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL '7 days'
                    AND metadata->>'status' = 'success'
                    ORDER BY RANDOM()
                    LIMIT 10
                """),
                {"org_id": organization_id}
            ).fetchall()
            sample_urls = [row.url for row in sample_result]
        
        if not sample_urls:
            raise HTTPException(status_code=404, detail="No recent crawled pages found for analysis")
        
        # Initialize visual analyzer
        from connectors.web_scraper_connector import VisualContentAnalyzer
        import aiohttp
        from bs4 import BeautifulSoup
        
        visual_analyzer = VisualContentAnalyzer()
        analysis_results = []
        
        # Analyze each URL (simplified - in production would fetch fresh content)
        for url in sample_urls[:5]:  # Limit to 5 for performance
            try:
                # Get existing page data
                page_data = db.execute(
                    text("""
                        SELECT content, metadata FROM crawled_pages 
                        WHERE url = :url AND organization_id = :org_id
                        ORDER BY last_crawled DESC LIMIT 1
                    """),
                    {"url": url, "org_id": organization_id}
                ).fetchone()
                
                if page_data and page_data.content:
                    soup = BeautifulSoup(page_data.content, 'html.parser')
                    visual_analysis = await visual_analyzer.analyze_page_visuals(soup, url)
                    analysis_results.append(visual_analysis)
                    
            except Exception as e:
                logger.warning(f"Error analyzing visual content for {url}: {e}")
                analysis_results.append({
                    'url': url,
                    'error': str(e),
                    'analysis_timestamp': datetime.utcnow().isoformat()
                })
        
        # Generate summary insights
        total_images = sum(result.get('image_analysis', {}).get('total_images', 0) 
                          for result in analysis_results if 'image_analysis' in result)
        
        accessibility_scores = [result.get('accessibility_score', {}).get('score', 0) 
                               for result in analysis_results if 'accessibility_score' in result]
        avg_accessibility = sum(accessibility_scores) / len(accessibility_scores) if accessibility_scores else 0
        
        layout_quality_counts = {}
        for result in analysis_results:
            layout_quality = result.get('layout_analysis', {}).get('layout_quality', 'unknown')
            layout_quality_counts[layout_quality] = layout_quality_counts.get(layout_quality, 0) + 1
        
        # Log audit event
        AuditLogger.log_event(
            db, "visual_content_analysis", current_user["id"], "connectors", "read",
            f"Visual content analysis for connector {connector_id}",
            {"connector_id": connector_id, "urls_analyzed": len(analysis_results)}
        )
        
        return {
            "status": "success",
            "analysis_results": analysis_results,
            "summary_insights": {
                "total_urls_analyzed": len(analysis_results),
                "total_images_found": total_images,
                "average_accessibility_score": round(avg_accessibility, 2),
                "layout_quality_distribution": layout_quality_counts,
                "analysis_timestamp": datetime.utcnow().isoformat()
            },
            "recommendations": [
                "Improve accessibility scores below 0.8" if avg_accessibility < 0.8 else "Good accessibility compliance",
                "Optimize image loading for better performance" if total_images > 50 else "Image count within optimal range",
                "Consider responsive design improvements" if 'poor' in layout_quality_counts else "Layout structure looks good"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in visual content analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Visual analysis error: {str(e)}")


@router.post("/{connector_id}/smart-budget-allocation", response_model=Dict[str, Any])
async def allocate_crawl_budget(
    domain_id: str,
    connector_id: str,
    budget_config: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Smart crawl budget allocation and optimization"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Validate budget configuration
        total_budget = budget_config.get('total_budget', 1000)
        if total_budget < 10 or total_budget > 100000:
            raise HTTPException(status_code=400, detail="Total budget must be between 10 and 100,000 pages")
        
        # Initialize budget manager
        from connectors.web_scraper_connector import SmartCrawlBudgetManager
        budget_manager = SmartCrawlBudgetManager()
        
        # Allocate budget
        budget_allocation = await budget_manager.allocate_crawl_budget(
            db, organization_id, total_budget
        )
        
        # Generate optimized schedule
        schedule_optimization = await budget_manager.optimize_crawl_schedule(
            db, organization_id, budget_allocation.get('budget_allocation', {})
        )
        
        # Store budget allocation in connector config
        updated_config = {
            'budget_allocation': budget_allocation,
            'schedule_optimization': schedule_optimization,
            'last_budget_update': datetime.utcnow().isoformat()
        }
        
        db.execute(
            text("""
                UPDATE connectors 
                SET sync_config = COALESCE(sync_config, '{}')::jsonb || :budget_config::jsonb,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {
                "connector_id": connector_id,
                "org_id": organization_id,
                "budget_config": json.dumps(updated_config)
            }
        )
        
        # Log audit event
        AuditLogger.log_event(
            db, "budget_allocation", current_user["id"], "connectors", "update",
            f"Smart budget allocation for connector {connector_id}",
            {"connector_id": connector_id, "total_budget": total_budget}
        )
        
        return {
            "status": "success",
            "budget_allocation": budget_allocation,
            "schedule_optimization": schedule_optimization,
            "implementation_steps": [
                "Budget allocation has been calculated and saved",
                "Optimized crawl schedule has been generated",
                "Next crawl will use the new budget parameters",
                "Review allocation weekly for best results"
            ],
            "next_actions": [
                "Start scheduled crawl with new budget",
                "Monitor budget utilization",
                "Adjust allocation based on performance"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error in smart budget allocation: {e}")
        raise HTTPException(status_code=500, detail=f"Budget allocation error: {str(e)}")


@router.get("/{connector_id}/change-detection-report", response_model=Dict[str, Any])
async def get_content_change_report(
    domain_id: str,
    connector_id: str,
    time_range_days: int = Query(7, ge=1, le=90, description="Time range for change analysis"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Real-time content change detection and monitoring report"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Get pages with multiple crawl history for change detection
        pages_with_history = db.execute(
            text("""
                WITH page_versions AS (
                    SELECT 
                        url,
                        content_hash,
                        metadata,
                        title,
                        word_count,
                        last_crawled,
                        ROW_NUMBER() OVER (PARTITION BY url ORDER BY last_crawled DESC) as version_rank
                    FROM crawled_pages 
                    WHERE organization_id = :org_id
                    AND last_crawled > NOW() - INTERVAL ':days days'
                )
                SELECT 
                    url,
                    COUNT(*) as version_count,
                    MAX(last_crawled) as latest_crawl,
                    MIN(last_crawled) as earliest_crawl
                FROM page_versions 
                GROUP BY url
                HAVING COUNT(*) > 1
                ORDER BY version_count DESC, latest_crawl DESC
                LIMIT 20
            """),
            {"org_id": organization_id, "days": time_range_days}
        ).fetchall()
        
        # Initialize change detector
        from connectors.web_scraper_connector import RealTimeChangeDetector
        change_detector = RealTimeChangeDetector()
        
        change_analysis_results = []
        total_changes_detected = 0
        change_types_summary = {}
        
        # Analyze each page for changes
        for page in pages_with_history:
            try:
                # Get latest version details
                latest_version = db.execute(
                    text("""
                        SELECT content, metadata, title, word_count, content_hash
                        FROM crawled_pages 
                        WHERE url = :url AND organization_id = :org_id
                        ORDER BY last_crawled DESC
                        LIMIT 1
                    """),
                    {"url": page.url, "org_id": organization_id}
                ).fetchone()
                
                if latest_version:
                    # Simulate current content structure
                    current_content = {
                        'text_content': latest_version.content or '',
                        'metadata': json.loads(latest_version.metadata) if latest_version.metadata else {},
                        'title': latest_version.title,
                        'word_count': latest_version.word_count
                    }
                    
                    # Detect changes
                    change_analysis = await change_detector.detect_content_changes(
                        db, page.url, current_content
                    )
                    
                    change_analysis_results.append(change_analysis)
                    
                    if change_analysis.get('change_detected'):
                        total_changes_detected += 1
                        for change_type in change_analysis.get('change_types', []):
                            change_types_summary[change_type] = change_types_summary.get(change_type, 0) + 1
                            
            except Exception as e:
                logger.warning(f"Error analyzing changes for {page.url}: {e}")
                change_analysis_results.append({
                    'url': page.url,
                    'error': str(e),
                    'analysis_timestamp': datetime.utcnow().isoformat()
                })
        
        # Generate insights and recommendations
        change_frequency = total_changes_detected / len(pages_with_history) if pages_with_history else 0
        most_common_change = max(change_types_summary.items(), key=lambda x: x[1])[0] if change_types_summary else None
        
        insights = []
        if change_frequency > 0.5:
            insights.append("High content change activity detected - consider more frequent crawling")
        elif change_frequency < 0.1:
            insights.append("Low change activity - current crawl frequency may be sufficient")
        
        if most_common_change:
            insights.append(f"Most common change type: {most_common_change}")
        
        # Log audit event
        AuditLogger.log_event(
            db, "change_detection_report", current_user["id"], "connectors", "read",
            f"Content change detection report for connector {connector_id}",
            {"connector_id": connector_id, "pages_analyzed": len(change_analysis_results)}
        )
        
        return {
            "status": "success",
            "analysis_period": {
                "time_range_days": time_range_days,
                "pages_analyzed": len(change_analysis_results),
                "pages_with_changes": total_changes_detected
            },
            "change_detection_results": change_analysis_results,
            "summary_statistics": {
                "total_changes_detected": total_changes_detected,
                "change_frequency": round(change_frequency, 3),
                "change_types_distribution": change_types_summary,
                "most_active_pages": [
                    result['url'] for result in change_analysis_results 
                    if result.get('change_magnitude', 0) > 0.5
                ][:5]
            },
            "insights_and_recommendations": insights,
            "monitoring_suggestions": [
                "Set up alerts for high-magnitude changes",
                "Consider automated re-crawling for frequently changing pages",
                "Monitor semantic drift for content quality"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error generating change detection report: {e}")
        raise HTTPException(status_code=500, detail=f"Change detection error: {str(e)}")


@router.post("/{connector_id}/enhanced-crawl-session", response_model=Dict[str, Any])
async def start_enhanced_crawl_session(
    domain_id: str,
    connector_id: str,
    background_tasks: BackgroundTasks,
    enhanced_options: Dict[str, Any] = None,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:write"))
):
    """Start an enhanced crawl session with all advanced features enabled"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Get connector configuration
        connector = db.execute(
            text("""
                SELECT c.*, od.domain_name as domain_name
                FROM connectors c
                JOIN organization_domains od ON c.domain_id = od.id
                WHERE c.id = :connector_id AND c.organization_id = :org_id
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        if not connector:
            raise HTTPException(status_code=404, detail="Connector not found")
        
        # Create enhanced crawl session
        session_id = str(uuid.uuid4())
        
        # Default enhanced options
        default_options = {
            'enable_ai_curation': True,
            'enable_visual_analysis': True,
            'enable_change_detection': True,
            'enable_budget_optimization': True,
            'enable_competitive_intelligence': True,
            'enable_security_monitoring': True,
            'max_pages': enhanced_options.get('max_pages', 100) if enhanced_options else 100,
            'quality_threshold': 0.6,
            'enable_real_time_updates': True
        }
        
        if enhanced_options:
            default_options.update(enhanced_options)
        
        # Store session configuration
        session_config = {
            'session_id': session_id,
            'connector_id': connector_id,
            'organization_id': organization_id,
            'domain': connector.domain_name,
            'enhanced_options': default_options,
            'status': 'initializing',
            'created_at': datetime.utcnow().isoformat(),
            'created_by': current_user['id']
        }
        
        # Start background enhanced crawl task
        def run_enhanced_crawl():
            import asyncio
            
            async def enhanced_crawl_task():
                try:
                    # Import crawler components
                    from connectors.web_scraper_connector import (
                        WebScraperConnector, AIContentCurator, VisualContentAnalyzer,
                        SmartCrawlBudgetManager, RealTimeChangeDetector, CompetitiveIntelligence,
                        AdvancedSecurityMonitor
                    )
                    
                    # Initialize enhanced web scraper
                    from services.base_connector import ConnectorConfig
                    config = ConnectorConfig(
                        connector_type='web_scraper',
                        auth_config=json.loads(connector.auth_config) if connector.auth_config else {},
                        sync_config=json.loads(connector.sync_config) if connector.sync_config else {},
                        mapping_config=json.loads(connector.mapping_config) if connector.mapping_config else {}
                    )
                    
                    scraper = WebScraperConnector(config)
                    
                    # Update session status
                    session_config['status'] = 'running'
                    
                    # Execute enhanced crawl with all features
                    results = await scraper.crawl_with_advanced_pipeline(
                        db=db,
                        connector_id=connector_id,
                        organization_id=organization_id,
                        domain=connector.domain_name
                    )
                    
                    # Get additional insights
                    if default_options['enable_ai_curation']:
                        ai_curator = AIContentCurator()
                        trending_content = await ai_curator.discover_trending_content(
                            db, organization_id, connector.domain_name
                        )
                        results['ai_discoveries'] = trending_content[:10]
                    
                    if default_options['enable_competitive_intelligence']:
                        competitive_intel = CompetitiveIntelligence()
                        competitive_analysis = await competitive_intel.analyze_competitive_landscape(
                            db, organization_id
                        )
                        results['competitive_intelligence'] = competitive_analysis
                    
                    # Update session with results
                    session_config.update({
                        'status': 'completed',
                        'completed_at': datetime.utcnow().isoformat(),
                        'results_summary': {
                            'pages_processed': len(results.get('crawled_pages', [])),
                            'ai_discoveries': len(results.get('ai_discoveries', [])),
                            'quality_score': results.get('overall_quality_score', 0),
                            'features_enabled': list(default_options.keys())
                        }
                    })
                    
                    logger.info(f"Enhanced crawl session {session_id} completed successfully")
                    
                except Exception as e:
                    logger.error(f"Enhanced crawl session {session_id} failed: {e}")
                    session_config.update({
                        'status': 'failed',
                        'error': str(e),
                        'failed_at': datetime.utcnow().isoformat()
                    })
            
            asyncio.run(enhanced_crawl_task())
        
        background_tasks.add_task(run_enhanced_crawl)
        
        # Log audit event
        AuditLogger.log_event(
            db, "enhanced_crawl_session", current_user["id"], "connectors", "create",
            f"Started enhanced crawl session for connector {connector_id}",
            {"connector_id": connector_id, "session_id": session_id}
        )
        
        return {
            "status": "success",
            "session_id": session_id,
            "message": "Enhanced crawl session started successfully",
            "session_config": session_config,
            "enabled_features": [
                "AI-Powered Content Curation",
                "Visual Content Analysis",
                "Smart Budget Management",
                "Real-time Change Detection",
                "Competitive Intelligence Analysis",
                "Advanced Security Monitoring"
            ],
            "estimated_completion": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
            "monitoring_endpoints": {
                "session_status": f"/domains/{domain_id}/connectors/{connector_id}/crawl-session-status",
                "real_time_updates": f"/domains/{domain_id}/connectors/{connector_id}/session-updates/{session_id}"
            }
        }
        
    except Exception as e:
        logger.error(f"Error starting enhanced crawl session: {e}")
        raise HTTPException(status_code=500, detail=f"Enhanced crawl session error: {str(e)}")


@router.get("/{connector_id}/ml-content-insights", response_model=Dict[str, Any])
async def get_ml_content_insights(
    domain_id: str,
    connector_id: str,
    analysis_depth: str = Query("standard", regex="^(basic|standard|comprehensive)$"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_permission("connectors:read"))
):
    """Get machine learning-powered content insights and predictions"""
    try:
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
        
        organization_id = str(org_result.organization_id)
        
        # Get recent content for ML analysis
        recent_content = db.execute(
            text("""
                SELECT 
                    url,
                    title,
                    content,
                    word_count,
                    metadata,
                    last_crawled
                FROM crawled_pages 
                WHERE organization_id = :org_id
                AND last_crawled > NOW() - INTERVAL '30 days'
                AND metadata->>'status' = 'success'
                AND word_count > 50
                ORDER BY last_crawled DESC
                LIMIT 100
            """),
            {"org_id": organization_id}
        ).fetchall()
        
        if not recent_content:
            raise HTTPException(status_code=404, detail="No recent content found for ML analysis")
        
        # Initialize ML classifier
        from connectors.web_scraper_connector import MLContentClassifier
        from bs4 import BeautifulSoup
        
        ml_classifier = MLContentClassifier()
        
        # Analyze content with ML
        content_predictions = []
        quality_distribution = {'high': 0, 'medium': 0, 'low': 0}
        content_type_distribution = {}
        feature_importance_aggregate = {}
        
        for content in recent_content[:50]:  # Limit for performance
            try:
                # Parse content for feature extraction
                soup = BeautifulSoup(content.content or '', 'html.parser')
                text_content = soup.get_text()
                
                # Extract ML features
                features = ml_classifier.extract_features(
                    text_content, 
                    json.loads(content.metadata) if content.metadata else {},
                    soup
                )
                
                # Get ML predictions
                predictions = ml_classifier.predict_content_quality(features)
                
                content_predictions.append({
                    'url': content.url,
                    'title': content.title,
                    'predicted_quality': predictions['quality_score'],
                    'predicted_type': predictions['predicted_type'],
                    'confidence': predictions['confidence'],
                    'quality_reasons': predictions['quality_reasons']
                })
                
                # Update distributions
                quality_score = predictions['quality_score']
                if quality_score > 0.7:
                    quality_distribution['high'] += 1
                elif quality_score > 0.4:
                    quality_distribution['medium'] += 1
                else:
                    quality_distribution['low'] += 1
                
                content_type = predictions['predicted_type']
                content_type_distribution[content_type] = content_type_distribution.get(content_type, 0) + 1
                
                # Aggregate feature importance
                for feature, importance in predictions['feature_importance'].items():
                    if feature not in feature_importance_aggregate:
                        feature_importance_aggregate[feature] = []
                    feature_importance_aggregate[feature].append(importance)
                    
            except Exception as e:
                logger.warning(f"Error in ML analysis for {content.url}: {e}")
                continue
        
        # Calculate aggregate insights
        avg_feature_importance = {}
        for feature, values in feature_importance_aggregate.items():
            avg_feature_importance[feature] = sum(values) / len(values) if values else 0
        
        # Generate ML-powered recommendations
        ml_recommendations = []
        
        high_quality_ratio = quality_distribution['high'] / max(1, len(content_predictions))
        if high_quality_ratio < 0.3:
            ml_recommendations.append("Focus crawling on higher quality content sources")
        
        most_common_type = max(content_type_distribution.items(), key=lambda x: x[1])[0] if content_type_distribution else None
        if most_common_type:
            ml_recommendations.append(f"Content type '{most_common_type}' is most prevalent - optimize for this category")
        
        # Advanced insights for comprehensive analysis
        advanced_insights = {}
        if analysis_depth == "comprehensive":
            # Content evolution patterns
            time_series_analysis = []
            # Predictive quality trends
            quality_forecast = {"trend": "stable", "confidence": 0.7}
            # Content gap analysis
            content_gaps = ["More technical documentation needed", "Increase visual content coverage"]
            
            advanced_insights = {
                'time_series_analysis': time_series_analysis,
                'quality_forecast': quality_forecast,
                'content_gaps': content_gaps,
                'optimization_potential': "Medium-High"
            }
        
        # Log audit event
        AuditLogger.log_event(
            db, "ml_content_insights", current_user["id"], "connectors", "read",
            f"ML content insights for connector {connector_id}",
            {"connector_id": connector_id, "analysis_depth": analysis_depth}
        )
        
        return {
            "status": "success",
            "analysis_summary": {
                "total_content_analyzed": len(content_predictions),
                "analysis_depth": analysis_depth,
                "ml_model_version": "2.0",
                "analysis_timestamp": datetime.utcnow().isoformat()
            },
            "content_predictions": content_predictions[:20],  # Return top 20
            "quality_distribution": quality_distribution,
            "content_type_distribution": content_type_distribution,
            "feature_importance": avg_feature_importance,
            "ml_recommendations": ml_recommendations,
            "advanced_insights": advanced_insights,
            "actionable_steps": [
                "Review low-quality content for improvement opportunities",
                "Prioritize crawling of high-confidence, high-quality sources",
                "Monitor content type distribution for balanced coverage",
                "Use feature importance to optimize content selection criteria"
            ]
        }
        
    except Exception as e:
        logger.error(f"Error generating ML content insights: {e}")
        raise HTTPException(status_code=500, detail=f"ML insights error: {str(e)}")


@router.websocket("/{connector_id}/crawl-progress")
async def crawl_progress_websocket(
    websocket: WebSocket,
    domain_id: str,
    connector_id: str,
    token: str = Query(..., description="JWT token for authentication")
):
    """WebSocket endpoint for real-time crawl progress updates"""
    await websocket.accept()
    
    try:
        # TODO: Add proper JWT authentication here
        # For now, we'll skip auth but in production you should validate the JWT token
        
        # Get database session
        from dependencies import get_db
        db = next(get_db())
        
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "message": "Connected to crawl progress stream",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Monitor crawl progress every 1 second
        last_count = 0
        last_sync_job_check = datetime.utcnow()
        
        while True:
            try:
                current_time = datetime.utcnow()
                
                # Check if there's an active sync job every 5 seconds
                if (current_time - last_sync_job_check).seconds >= 5:
                    active_sync = db.execute(
                        text("""
                            SELECT sj.id, sj.status, sj.started_at, sj.metadata
                            FROM sync_jobs sj
                            WHERE sj.connector_id = :connector_id 
                            AND sj.status IN ('pending', 'running')
                            ORDER BY sj.started_at DESC
                            LIMIT 1
                        """),
                        {"connector_id": connector_id}
                    ).fetchone()
                    
                    if active_sync:
                        await websocket.send_json({
                            "type": "sync_status",
                            "sync_job_id": str(active_sync.id),
                            "status": active_sync.status,
                            "started_at": active_sync.started_at.isoformat() if active_sync.started_at else None,
                            "metadata": active_sync.metadata,
                            "timestamp": current_time.isoformat()
                        })
                    
                    last_sync_job_check = current_time
                
                # Get current crawled pages count and recent activity
                crawl_stats = db.execute(
                    text("""
                        SELECT 
                            COUNT(*) as total_pages,
                            COUNT(CASE WHEN cp.last_crawled > NOW() - INTERVAL '1 minute' THEN 1 END) as recent_pages,
                            MAX(cp.last_crawled) as last_activity
                        FROM crawled_pages cp
                        JOIN connectors c ON cp.domain_id = c.domain_id
                        WHERE c.id = :connector_id
                    """),
                    {"connector_id": connector_id}
                ).fetchone()
                
                total_pages = crawl_stats.total_pages or 0
                recent_pages = crawl_stats.recent_pages or 0
                
                # Send progress update if there's new activity
                if total_pages != last_count or recent_pages > 0:
                    # Get the most recent pages crawled in the last minute
                    recent_crawled = db.execute(
                        text("""
                            SELECT cp.url, cp.title, cp.status, cp.last_crawled
                            FROM crawled_pages cp
                            JOIN connectors c ON cp.domain_id = c.domain_id
                            WHERE c.id = :connector_id 
                            AND cp.last_crawled > NOW() - INTERVAL '1 minute'
                            ORDER BY cp.last_crawled DESC
                            LIMIT 5
                        """),
                        {"connector_id": connector_id}
                    ).fetchall()
                    
                    await websocket.send_json({
                        "type": "crawl_progress",
                        "total_pages": total_pages,
                        "new_pages": total_pages - last_count,
                        "recent_activity": recent_pages,
                        "last_activity": crawl_stats.last_activity.isoformat() if crawl_stats.last_activity else None,
                        "recent_pages": [
                            {
                                "url": page.url,
                                "title": page.title,
                                "status": page.status,
                                "crawled_at": page.last_crawled.isoformat() if page.last_crawled else None
                            }
                            for page in recent_crawled
                        ],
                        "timestamp": current_time.isoformat()
                    })
                    
                    last_count = total_pages
                
                # Wait 1 second before next check
                await asyncio.sleep(1)
                
            except Exception as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Error getting crawl progress: {str(e)}",
                    "timestamp": datetime.utcnow().isoformat()
                })
                await asyncio.sleep(5)  # Wait longer on error
                
    except WebSocketDisconnect:
        print(f"WebSocket disconnected for connector {connector_id}")
    except Exception as e:
        print(f"WebSocket error for connector {connector_id}: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Connection error: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            })
        except:
            pass