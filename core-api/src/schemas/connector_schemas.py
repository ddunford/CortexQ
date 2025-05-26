"""
Pydantic schemas for Data Source Connectors API
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class ConnectorType(str, Enum):
    """Supported connector types"""
    JIRA = "jira"
    GITHUB = "github"
    CONFLUENCE = "confluence"
    HUBSPOT = "hubspot"
    BITBUCKET = "bitbucket"
    SLACK = "slack"
    GOOGLE_DRIVE = "google_drive"
    WEB_SCRAPER = "web_scraper"


class ConnectorStatus(str, Enum):
    """Connector status values"""
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    SYNCING = "syncing"
    ERROR = "error"
    PENDING = "pending"


class SyncStatus(str, Enum):
    """Sync job status values"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class SyncFrequency(str, Enum):
    """Sync frequency options"""
    REALTIME = "realtime"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"
    MANUAL = "manual"


class AuthType(str, Enum):
    """Authentication types"""
    OAUTH = "oauth"
    API_KEY = "api_key"
    BASIC = "basic"


# ============================================================================
# AUTH CONFIGURATION SCHEMAS
# ============================================================================

class AuthConfigBase(BaseModel):
    """Base authentication configuration"""
    type: AuthType
    

class OAuthConfig(AuthConfigBase):
    """OAuth authentication configuration"""
    type: AuthType = AuthType.OAUTH
    client_id: str
    client_secret: str
    scopes: List[str] = []
    redirect_uri: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[datetime] = None


class ApiKeyConfig(AuthConfigBase):
    """API Key authentication configuration"""
    type: AuthType = AuthType.API_KEY
    api_key: str
    api_secret: Optional[str] = None
    username: Optional[str] = None


class BasicAuthConfig(AuthConfigBase):
    """Basic authentication configuration"""
    type: AuthType = AuthType.BASIC
    username: str
    password: str


# ============================================================================
# SYNC CONFIGURATION SCHEMAS
# ============================================================================

class SyncConfig(BaseModel):
    """Sync configuration"""
    frequency: SyncFrequency = SyncFrequency.DAILY
    schedule: Optional[str] = None  # Cron expression
    batch_size: int = Field(default=100, ge=1, le=1000)
    enable_incremental_sync: bool = True
    sync_filters: Dict[str, Any] = Field(default_factory=dict)
    max_records: Optional[int] = None


# ============================================================================
# FIELD MAPPING SCHEMAS
# ============================================================================

class FieldMapping(BaseModel):
    """Field mapping configuration"""
    source_field: str
    target_field: str
    transformation: Optional[str] = None
    required: bool = False


class MappingConfig(BaseModel):
    """Complete mapping configuration"""
    mappings: List[FieldMapping] = Field(default_factory=list)
    default_values: Dict[str, Any] = Field(default_factory=dict)
    transformations: Dict[str, str] = Field(default_factory=dict)


# ============================================================================
# CONNECTOR SCHEMAS
# ============================================================================

class ConnectorBase(BaseModel):
    """Base connector schema"""
    name: str = Field(..., min_length=1, max_length=255)
    connector_type: ConnectorType
    is_enabled: bool = True


class ConnectorCreate(ConnectorBase):
    """Schema for creating a new connector"""
    auth_config: Dict[str, Any]
    sync_config: SyncConfig
    mapping_config: Optional[MappingConfig] = None


class ConnectorUpdate(BaseModel):
    """Schema for updating a connector"""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    is_enabled: Optional[bool] = None
    auth_config: Optional[Dict[str, Any]] = None
    sync_config: Optional[SyncConfig] = None
    mapping_config: Optional[MappingConfig] = None


class ConnectorResponse(ConnectorBase):
    """Schema for connector response"""
    id: str
    organization_id: str
    domain: str  # Domain name from JOIN with organization_domains
    last_sync_at: Optional[datetime] = None
    last_sync_status: Optional[str] = None
    sync_error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    status: ConnectorStatus = ConnectorStatus.PENDING
    
    class Config:
        from_attributes = True


# ============================================================================
# SYNC JOB SCHEMAS
# ============================================================================

class SyncJobCreate(BaseModel):
    """Schema for creating a sync job"""
    connector_id: str
    metadata: Optional[Dict[str, Any]] = None


class SyncJobResponse(BaseModel):
    """Schema for sync job response"""
    id: str
    connector_id: str
    organization_id: str
    status: SyncStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# OAUTH FLOW SCHEMAS
# ============================================================================

class OAuthInitiateRequest(BaseModel):
    """Schema for initiating OAuth flow"""
    connector_type: ConnectorType
    domain: str
    redirect_uri: Optional[str] = None


class OAuthInitiateResponse(BaseModel):
    """Schema for OAuth initiation response"""
    auth_url: str
    state: str


class OAuthCallbackRequest(BaseModel):
    """Schema for OAuth callback"""
    code: str
    state: str


class OAuthCallbackResponse(BaseModel):
    """Schema for OAuth callback response"""
    success: bool
    connector_id: Optional[str] = None
    message: str


# ============================================================================
# CONNECTOR TEST SCHEMAS
# ============================================================================

class ConnectorTestResponse(BaseModel):
    """Schema for connector test response"""
    success: bool
    connection_details: Optional[Dict[str, Any]] = None
    error_details: Optional[Dict[str, Any]] = None
    requires_reauth: bool = False
    tested_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# SYNC OPERATION SCHEMAS
# ============================================================================

class SyncRequest(BaseModel):
    """Schema for manual sync request"""
    full_sync: bool = False
    filters: Optional[Dict[str, Any]] = None


class SyncResponse(BaseModel):
    """Schema for sync response"""
    job_id: str
    status: SyncStatus
    message: str
    estimated_duration: Optional[int] = None  # seconds


# ============================================================================
# CONNECTOR STATISTICS SCHEMAS
# ============================================================================

class ConnectorStats(BaseModel):
    """Schema for connector statistics"""
    total_records: int = 0
    last_sync_records: int = 0
    sync_success_rate: float = 0.0
    average_sync_duration: Optional[int] = None  # seconds
    last_successful_sync: Optional[datetime] = None
    total_sync_jobs: int = 0
    failed_sync_jobs: int = 0


class ConnectorStatsResponse(ConnectorStats):
    """Schema for connector statistics response"""
    total_created: int = 0
    total_updated: int = 0
    successful_sync_jobs: int = 0


class ConnectorListResponse(BaseModel):
    """Schema for connector list response"""
    connectors: List[ConnectorResponse]
    total: int
    skip: int = 0
    limit: int = 20


# ============================================================================
# ERROR SCHEMAS
# ============================================================================

class ConnectorError(BaseModel):
    """Schema for connector errors"""
    error_code: str
    error_message: str
    error_details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# WEBHOOK SCHEMAS
# ============================================================================

class WebhookEvent(BaseModel):
    """Schema for webhook events"""
    event_type: str
    connector_id: str
    organization_id: str
    data: Dict[str, Any]
    timestamp: datetime = Field(default_factory=datetime.utcnow) 