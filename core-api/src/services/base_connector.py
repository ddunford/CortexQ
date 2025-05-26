"""
Base Connector Abstract Class
Defines the interface that all connector implementations must follow
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from schemas.connector_schemas import ConnectorType, SyncStatus


class SyncResultStatus(str, Enum):
    """Sync result status values"""
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    FAILURE = "failure"


@dataclass
class SyncResult:
    """Result of a sync operation"""
    status: SyncResultStatus
    records_processed: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_failed: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class ConnectorConfig:
    """Configuration for a connector instance"""
    id: str
    organization_id: str
    domain: str
    connector_type: ConnectorType
    name: str
    auth_config: Dict[str, Any]
    sync_config: Dict[str, Any]
    mapping_config: Optional[Dict[str, Any]] = None
    is_enabled: bool = True


@dataclass
class Document:
    """Document structure for imported data"""
    title: str
    content: str
    source_id: str
    source_type: str
    metadata: Dict[str, Any]
    organization_id: str
    domain: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()


class BaseConnector(ABC):
    """
    Abstract base class for all connector implementations
    
    Each connector type (Jira, GitHub, etc.) must implement this interface
    """
    
    def __init__(self, config: ConnectorConfig):
        """Initialize connector with configuration"""
        self.config = config
        self.connector_type = config.connector_type
        self.auth_config = config.auth_config
        self.sync_config = config.sync_config
        self.mapping_config = config.mapping_config or {}
        
    @abstractmethod
    async def authenticate(self) -> Tuple[bool, Optional[str]]:
        """
        Authenticate with the external service
        
        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        pass
    
    @abstractmethod
    async def test_connection(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Test connection to the external service
        
        Returns:
            Tuple of (success: bool, connection_details: Dict)
        """
        pass
    
    @abstractmethod
    async def fetch_data(self, since: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Fetch data from the external service
        
        Args:
            since: Optional datetime for incremental sync
            
        Returns:
            List of raw data records from external service
        """
        pass
    
    @abstractmethod
    async def transform_data(self, raw_data: List[Dict[str, Any]]) -> List[Document]:
        """
        Transform external data to internal Document format
        
        Args:
            raw_data: Raw data from external service
            
        Returns:
            List of transformed Document objects
        """
        pass
    
    async def sync(self, full_sync: bool = False) -> SyncResult:
        """
        Complete synchronization process
        
        Args:
            full_sync: Whether to perform full sync or incremental
            
        Returns:
            SyncResult with operation details
        """
        try:
            # Step 1: Authenticate
            auth_success, auth_error = await self.authenticate()
            if not auth_success:
                return SyncResult(
                    status=SyncResultStatus.FAILURE,
                    error_message=f"Authentication failed: {auth_error}"
                )
            
            # Step 2: Determine sync start point
            since = None if full_sync else await self._get_last_sync_time()
            
            # Step 3: Fetch data
            raw_data = await self.fetch_data(since=since)
            
            # Step 4: Transform data
            documents = await self.transform_data(raw_data)
            
            # Step 5: Store documents
            result = await self._store_documents(documents)
            
            # Step 6: Update sync timestamp
            await self._update_last_sync_time()
            
            return result
            
        except Exception as e:
            return SyncResult(
                status=SyncResultStatus.FAILURE,
                error_message=str(e)
            )
    
    async def _get_last_sync_time(self) -> Optional[datetime]:
        """Get the timestamp of the last successful sync"""
        # This would query the database for the last sync time
        # Implementation depends on database access pattern
        return None
    
    async def _store_documents(self, documents: List[Document]) -> SyncResult:
        """Store transformed documents in the database"""
        # This would store documents and generate embeddings
        # Implementation depends on database access pattern
        return SyncResult(
            status=SyncResultStatus.SUCCESS,
            records_processed=len(documents),
            records_created=len(documents)
        )
    
    async def _update_last_sync_time(self):
        """Update the last sync timestamp for this connector"""
        # This would update the connector's last_sync_at field
        pass
    
    def _apply_field_mapping(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Apply field mappings to transform external data structure"""
        if not self.mapping_config or not self.mapping_config.get('mappings'):
            return data
        
        mapped_data = {}
        mappings = self.mapping_config.get('mappings', [])
        
        for mapping in mappings:
            source_field = mapping.get('source_field')
            target_field = mapping.get('target_field')
            transformation = mapping.get('transformation')
            
            if source_field in data:
                value = data[source_field]
                
                # Apply transformation if specified
                if transformation:
                    value = self._apply_transformation(value, transformation)
                
                mapped_data[target_field] = value
        
        # Apply default values
        default_values = self.mapping_config.get('default_values', {})
        for field, default_value in default_values.items():
            if field not in mapped_data:
                mapped_data[field] = default_value
        
        return mapped_data
    
    def _apply_transformation(self, value: Any, transformation: str) -> Any:
        """Apply a transformation function to a field value"""
        # Simple transformation examples
        if transformation == "lowercase":
            return str(value).lower() if value else value
        elif transformation == "uppercase":
            return str(value).upper() if value else value
        elif transformation == "strip":
            return str(value).strip() if value else value
        elif transformation == "date_iso":
            if isinstance(value, datetime):
                return value.isoformat()
            return value
        else:
            return value
    
    def _get_sync_filters(self) -> Dict[str, Any]:
        """Get sync filters from configuration"""
        return self.sync_config.get('sync_filters', {})
    
    def _get_batch_size(self) -> int:
        """Get batch size from configuration"""
        return self.sync_config.get('batch_size', 100)
    
    def _should_include_record(self, record: Dict[str, Any]) -> bool:
        """Check if a record should be included based on sync filters"""
        filters = self._get_sync_filters()
        
        for field, filter_value in filters.items():
            if field in record:
                record_value = record[field]
                
                # Simple equality check
                if isinstance(filter_value, (str, int, bool)):
                    if record_value != filter_value:
                        return False
                
                # List membership check
                elif isinstance(filter_value, list):
                    if record_value not in filter_value:
                        return False
                
                # Range check for dates/numbers
                elif isinstance(filter_value, dict):
                    if 'min' in filter_value and record_value < filter_value['min']:
                        return False
                    if 'max' in filter_value and record_value > filter_value['max']:
                        return False
        
        return True 