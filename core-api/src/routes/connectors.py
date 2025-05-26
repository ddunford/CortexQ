"""
Connector API Routes
Handles all data source connector operations
"""

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
import json
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid

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
            connector_type=ConnectorType(conn.connector_type),
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
            SELECT c.*, od.domain_name 
            FROM connectors c 
            JOIN organization_domains od ON c.domain_id = od.id 
            WHERE c.id = :connector_id AND c.organization_id = :org_id AND c.domain_id = :domain_id
        """),
        {
            "connector_id": connector_id,
            "org_id": organization_id,
            "domain_id": domain_id
        }
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
        params["auth_config"] = connector_data.auth_config
    
    if connector_data.sync_config is not None:
        update_fields.append("sync_config = :sync_config")
        params["sync_config"] = connector_data.sync_config.dict()
    
    if connector_data.mapping_config is not None:
        update_fields.append("mapping_config = :mapping_config")
        params["mapping_config"] = connector_data.mapping_config
    
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
    current_user: dict = Depends(require_permission("connectors:delete"))
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