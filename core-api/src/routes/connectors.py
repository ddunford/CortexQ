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
import re

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
            SELECT c.*, od.name as domain_name
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
        from ..connectors.web_scraper_connector import WebScraperConnector
        from ..connectors.base_connector import ConnectorConfig
        
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
        from ..connectors.web_scraper_connector import WebScraperConnector
        from ..connectors.base_connector import ConnectorConfig
        
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
            SELECT c.*, od.name as domain_name
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
                FROM crawled_pages 
                WHERE connector_id = :connector_id AND organization_id = :org_id
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
            SELECT c.*, od.name as domain_name
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
        # Build dynamic query
        where_conditions = ["connector_id = :connector_id", "organization_id = :org_id"]
        query_params = {
            "connector_id": connector_id,
            "org_id": organization_id,
            "offset": (page - 1) * page_size,
            "limit": page_size
        }
        
        if status_filter:
            where_conditions.append("status = :status_filter")
            query_params["status_filter"] = status_filter
        
        if search_query:
            where_conditions.append("(title ILIKE :search OR url ILIKE :search OR content ILIKE :search)")
            query_params["search"] = f"%{search_query}%"
        
        where_clause = " AND ".join(where_conditions)
        
        # Get total count
        total_count = db.execute(
            text(f"""
                SELECT COUNT(*) as count
                FROM crawled_pages 
                WHERE {where_clause}
            """),
            query_params
        ).fetchone().count
        
        # Get pages
        pages = db.execute(
            text(f"""
                SELECT 
                    id, url, title, status, word_count, content_hash,
                    last_crawled, depth, content_type, file_size, error_message,
                    CASE 
                        WHEN LENGTH(content) > 200 THEN SUBSTRING(content FROM 1 FOR 200) || '...'
                        ELSE content
                    END as content_preview
                FROM crawled_pages 
                WHERE {where_clause}
                ORDER BY last_crawled DESC
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
                SELECT url FROM crawled_pages 
                WHERE id = :page_id AND connector_id = :connector_id AND organization_id = :org_id
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
                WHERE id = :page_id AND connector_id = :connector_id AND organization_id = :org_id
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
        from connectors.base_connector import ConnectorConfig
        
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
        from connectors.base_connector import ConnectorConfig
        
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
        from connectors.base_connector import ConnectorConfig
        
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
        optimization_data = await scraper.optimize_crawl_settings(db, connector_id, organization_id)
        
        return {
            "success": True,
            "message": "Optimization suggestions retrieved successfully",
            **optimization_data
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
            SELECT c.*, od.name as domain_name
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
        from ..connectors.web_scraper_connector import WebScraperConnector
        from ..connectors.base_connector import ConnectorConfig
        
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
            SELECT c.*, od.name as domain_name
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
        from ..connectors.web_scraper_connector import WebScraperConnector
        from ..connectors.base_connector import ConnectorConfig
        
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
            SELECT c.*, od.name as domain_name
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
        from ..connectors.web_scraper_connector import WebScraperConnector
        from ..connectors.base_connector import ConnectorConfig
        
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
        
        # Start intelligent crawl in background
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
        
        # Merge with existing auth_config
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
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update enhanced configuration: {str(e)}")


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