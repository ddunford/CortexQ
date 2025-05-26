"""
Connector Service
Main service for managing data source connectors
"""

from typing import Dict, Any, Optional, Type
from sqlalchemy.orm import Session
from sqlalchemy import text

from services.base_connector import BaseConnector, ConnectorConfig
from services.oauth_service import OAuthService
from connectors.jira_connector import JiraConnector
from schemas.connector_schemas import ConnectorType, ConnectorResponse
from models import Connector, SyncJob


class ConnectorService:
    """Service for managing data source connectors"""
    
    # Registry of available connector implementations
    CONNECTOR_REGISTRY: Dict[ConnectorType, Type[BaseConnector]] = {
        ConnectorType.JIRA: JiraConnector,
        # TODO: Add other connector implementations
        # ConnectorType.GITHUB: GitHubConnector,
        # ConnectorType.CONFLUENCE: ConfluenceConnector,
        # ConnectorType.SLACK: SlackConnector,
    }
    
    def __init__(self, db: Session, oauth_service: OAuthService):
        """Initialize connector service"""
        self.db = db
        self.oauth_service = oauth_service
    
    def create_connector_instance(self, connector_data: Dict[str, Any]) -> BaseConnector:
        """Create a connector instance from database data"""
        connector_type = ConnectorType(connector_data["connector_type"])
        
        if connector_type not in self.CONNECTOR_REGISTRY:
            raise ValueError(f"Unsupported connector type: {connector_type}")
        
        # Create connector configuration
        config = ConnectorConfig(
            id=str(connector_data["id"]),
            organization_id=str(connector_data["organization_id"]),
            domain=connector_data["domain"],
            connector_type=connector_type,
            name=connector_data["name"],
            auth_config=connector_data["auth_config"],
            sync_config=connector_data["sync_config"],
            mapping_config=connector_data.get("mapping_config"),
            is_enabled=connector_data["is_enabled"]
        )
        
        # Get connector class and create instance
        connector_class = self.CONNECTOR_REGISTRY[connector_type]
        return connector_class(config)
    
    async def test_connector_connection(self, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Test connection for a specific connector"""
        # Get connector from database
        connector_data = self._get_connector_data(connector_id, organization_id)
        if not connector_data:
            raise ValueError("Connector not found")
        
        # Ensure valid authentication
        connector_type = ConnectorType(connector_data["connector_type"])
        auth_config = await self._ensure_valid_auth(connector_type, connector_data["auth_config"])
        
        if not auth_config:
            return {
                "success": False,
                "error": "Authentication failed or expired",
                "requires_reauth": True
            }
        
        # Update auth config if it was refreshed
        if auth_config != connector_data["auth_config"]:
            await self._update_connector_auth(connector_id, auth_config)
            connector_data["auth_config"] = auth_config
        
        # Create connector instance and test
        connector = self.create_connector_instance(connector_data)
        success, details = await connector.test_connection()
        
        return {
            "success": success,
            "connection_details": details if success else None,
            "error_details": details if not success else None,
            "requires_reauth": False
        }
    
    async def sync_connector(self, connector_id: str, organization_id: str, full_sync: bool = False) -> Dict[str, Any]:
        """Trigger sync for a specific connector"""
        # Get connector from database
        connector_data = self._get_connector_data(connector_id, organization_id)
        if not connector_data:
            raise ValueError("Connector not found")
        
        if not connector_data["is_enabled"]:
            raise ValueError("Connector is disabled")
        
        # Ensure valid authentication
        connector_type = ConnectorType(connector_data["connector_type"])
        auth_config = await self._ensure_valid_auth(connector_type, connector_data["auth_config"])
        
        if not auth_config:
            raise ValueError("Authentication failed or expired")
        
        # Update auth config if it was refreshed
        if auth_config != connector_data["auth_config"]:
            await self._update_connector_auth(connector_id, auth_config)
            connector_data["auth_config"] = auth_config
        
        # Create sync job record
        sync_job_id = await self._create_sync_job(connector_id, organization_id, full_sync)
        
        try:
            # Update sync job status to running
            await self._update_sync_job_status(sync_job_id, "running")
            
            # Create connector instance and perform sync
            connector = self.create_connector_instance(connector_data)
            sync_result = await connector.sync(full_sync=full_sync)
            
            # Update connector last sync info
            await self._update_connector_sync_status(
                connector_id, 
                sync_result.status.value,
                sync_result.error_message
            )
            
            # Update sync job with results
            await self._complete_sync_job(sync_job_id, sync_result)
            
            return {
                "success": sync_result.status.value in ["success", "partial_success"],
                "sync_job_id": sync_job_id,
                "records_processed": sync_result.records_processed,
                "records_created": sync_result.records_created,
                "records_updated": sync_result.records_updated,
                "error_message": sync_result.error_message
            }
            
        except Exception as e:
            # Update sync job as failed
            await self._update_sync_job_status(sync_job_id, "failed", str(e))
            await self._update_connector_sync_status(connector_id, "error", str(e))
            
            return {
                "success": False,
                "sync_job_id": sync_job_id,
                "error_message": str(e)
            }
    
    async def get_connector_stats(self, connector_id: str, organization_id: str) -> Dict[str, Any]:
        """Get statistics for a connector"""
        stats = self.db.execute(
            text("""
                SELECT 
                    COUNT(sj.id) as total_sync_jobs,
                    COUNT(CASE WHEN sj.status = 'failed' THEN 1 END) as failed_sync_jobs,
                    COUNT(CASE WHEN sj.status = 'completed' THEN 1 END) as successful_sync_jobs,
                    AVG(CASE WHEN sj.status = 'completed' AND sj.started_at IS NOT NULL AND sj.completed_at IS NOT NULL 
                        THEN EXTRACT(EPOCH FROM (sj.completed_at - sj.started_at)) END) as avg_duration,
                    MAX(CASE WHEN sj.status = 'completed' THEN sj.completed_at END) as last_successful_sync,
                    SUM(CASE WHEN sj.status = 'completed' THEN sj.records_processed ELSE 0 END) as total_records,
                    SUM(CASE WHEN sj.status = 'completed' THEN sj.records_created ELSE 0 END) as total_created,
                    SUM(CASE WHEN sj.status = 'completed' THEN sj.records_updated ELSE 0 END) as total_updated
                FROM sync_jobs sj
                WHERE sj.connector_id = :connector_id 
                AND sj.organization_id = :org_id
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        if not stats:
            return {
                "total_records": 0,
                "sync_success_rate": 0.0,
                "total_sync_jobs": 0,
                "failed_sync_jobs": 0
            }
        
        success_rate = 0.0
        if stats.total_sync_jobs > 0:
            success_rate = (stats.successful_sync_jobs or 0) / stats.total_sync_jobs
        
        return {
            "total_records": stats.total_records or 0,
            "total_created": stats.total_created or 0,
            "total_updated": stats.total_updated or 0,
            "sync_success_rate": success_rate,
            "average_sync_duration": int(stats.avg_duration) if stats.avg_duration else None,
            "last_successful_sync": stats.last_successful_sync,
            "total_sync_jobs": stats.total_sync_jobs or 0,
            "failed_sync_jobs": stats.failed_sync_jobs or 0,
            "successful_sync_jobs": stats.successful_sync_jobs or 0
        }
    
    def get_supported_connector_types(self) -> Dict[str, Dict[str, Any]]:
        """Get list of supported connector types with their capabilities"""
        return {
            connector_type.value: {
                "name": connector_type.value.replace("_", " ").title(),
                "description": self._get_connector_description(connector_type),
                "auth_types": self._get_supported_auth_types(connector_type),
                "capabilities": self._get_connector_capabilities(connector_type)
            }
            for connector_type in self.CONNECTOR_REGISTRY.keys()
        }
    
    def _get_connector_data(self, connector_id: str, organization_id: str) -> Optional[Dict[str, Any]]:
        """Get connector data from database"""
        result = self.db.execute(
            text("""
                SELECT * FROM connectors 
                WHERE id = :connector_id AND organization_id = :org_id
            """),
            {"connector_id": connector_id, "org_id": organization_id}
        ).fetchone()
        
        if result:
            return {
                "id": result.id,
                "organization_id": result.organization_id,
                "domain": result.domain,
                "connector_type": result.connector_type,
                "name": result.name,
                "is_enabled": result.is_enabled,
                "auth_config": result.auth_config,
                "sync_config": result.sync_config,
                "mapping_config": result.mapping_config
            }
        return None
    
    async def _ensure_valid_auth(self, connector_type: ConnectorType, auth_config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Ensure authentication is valid, refreshing if necessary"""
        auth_type = auth_config.get("type")
        
        if auth_type == "oauth":
            # Check if token needs refresh
            return await self.oauth_service.ensure_valid_token(connector_type, auth_config)
        
        # For API key and basic auth, return as-is
        return auth_config
    
    async def _update_connector_auth(self, connector_id: str, auth_config: Dict[str, Any]):
        """Update connector authentication configuration"""
        self.db.execute(
            text("""
                UPDATE connectors 
                SET auth_config = :auth_config, updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id
            """),
            {"connector_id": connector_id, "auth_config": auth_config}
        )
        self.db.commit()
    
    async def _create_sync_job(self, connector_id: str, organization_id: str, full_sync: bool) -> str:
        """Create a new sync job record"""
        result = self.db.execute(
            text("""
                INSERT INTO sync_jobs (
                    connector_id, organization_id, status, metadata, started_at
                ) VALUES (
                    :connector_id, :org_id, 'pending', :metadata, CURRENT_TIMESTAMP
                ) RETURNING id
            """),
            {
                "connector_id": connector_id,
                "org_id": organization_id,
                "metadata": {"full_sync": full_sync, "trigger_type": "manual"}
            }
        ).fetchone()
        
        self.db.commit()
        return str(result.id)
    
    async def _update_sync_job_status(self, sync_job_id: str, status: str, error_message: Optional[str] = None):
        """Update sync job status"""
        update_fields = ["status = :status"]
        params = {"sync_job_id": sync_job_id, "status": status}
        
        if status == "running":
            update_fields.append("started_at = CURRENT_TIMESTAMP")
        elif status in ["completed", "failed"]:
            update_fields.append("completed_at = CURRENT_TIMESTAMP")
        
        if error_message:
            update_fields.append("error_message = :error_message")
            params["error_message"] = error_message
        
        query = f"""
            UPDATE sync_jobs 
            SET {', '.join(update_fields)}
            WHERE id = :sync_job_id
        """
        
        self.db.execute(text(query), params)
        self.db.commit()
    
    async def _complete_sync_job(self, sync_job_id: str, sync_result):
        """Complete sync job with results"""
        status = "completed" if sync_result.status.value == "success" else "failed"
        
        self.db.execute(
            text("""
                UPDATE sync_jobs 
                SET status = :status,
                    completed_at = CURRENT_TIMESTAMP,
                    records_processed = :records_processed,
                    records_created = :records_created,
                    records_updated = :records_updated,
                    error_message = :error_message,
                    metadata = metadata || :result_metadata
                WHERE id = :sync_job_id
            """),
            {
                "sync_job_id": sync_job_id,
                "status": status,
                "records_processed": sync_result.records_processed,
                "records_created": sync_result.records_created,
                "records_updated": sync_result.records_updated,
                "error_message": sync_result.error_message,
                "result_metadata": sync_result.metadata
            }
        )
        self.db.commit()
    
    async def _update_connector_sync_status(self, connector_id: str, status: str, error_message: Optional[str] = None):
        """Update connector's last sync status"""
        self.db.execute(
            text("""
                UPDATE connectors 
                SET last_sync_at = CURRENT_TIMESTAMP,
                    last_sync_status = :status,
                    sync_error_message = :error_message,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :connector_id
            """),
            {
                "connector_id": connector_id,
                "status": status,
                "error_message": error_message
            }
        )
        self.db.commit()
    
    def _get_connector_description(self, connector_type: ConnectorType) -> str:
        """Get description for a connector type"""
        descriptions = {
            ConnectorType.JIRA: "Import issues, comments, and project data from Atlassian Jira",
            ConnectorType.GITHUB: "Import repositories, issues, pull requests, and documentation from GitHub",
            ConnectorType.CONFLUENCE: "Import wiki pages, spaces, and documentation from Atlassian Confluence",
            ConnectorType.SLACK: "Import conversations, channels, and shared files from Slack",
            ConnectorType.GOOGLE_DRIVE: "Import documents, folders, and shared content from Google Drive"
        }
        return descriptions.get(connector_type, "Data source connector")
    
    def _get_supported_auth_types(self, connector_type: ConnectorType) -> list:
        """Get supported authentication types for a connector"""
        auth_types = {
            ConnectorType.JIRA: ["oauth", "api_key"],
            ConnectorType.GITHUB: ["oauth", "api_key"],
            ConnectorType.CONFLUENCE: ["oauth", "api_key"],
            ConnectorType.SLACK: ["oauth"],
            ConnectorType.GOOGLE_DRIVE: ["oauth"]
        }
        return auth_types.get(connector_type, ["api_key"])
    
    def _get_connector_capabilities(self, connector_type: ConnectorType) -> Dict[str, bool]:
        """Get capabilities for a connector type"""
        return {
            "incremental_sync": True,
            "full_sync": True,
            "real_time": False,  # Future enhancement
            "field_mapping": True,
            "filtering": True,
            "rate_limiting": True
        } 