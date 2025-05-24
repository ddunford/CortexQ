"""
Domain Configuration Management
"""

from typing import Dict, List, Optional
from pydantic import BaseModel
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
import uuid
from datetime import datetime

from database import Base

class DomainConfig(Base):
    """Domain configuration model"""
    __tablename__ = "domain_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_name = Column(String(50), unique=True, nullable=False)
    display_name = Column(String(100))
    description = Column(Text)
    embedding_model = Column(String(100), default='nomic-embed-text')
    similarity_threshold = Column(Float, default=0.7)
    max_results = Column(Integer, default=10)
    specialized_prompts = Column(JSONB, default={})
    vector_index_path = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class DomainPermission(Base):
    """Domain permission model"""
    __tablename__ = "domain_permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain_name = Column(String(50), nullable=False)
    role_name = Column(String(50), nullable=False)
    permissions = Column(ARRAY(String), default=['read'])
    created_at = Column(DateTime, default=datetime.utcnow)


class DomainSettings(BaseModel):
    """Pydantic model for domain settings"""
    domain_name: str
    display_name: str
    description: str = ""
    embedding_model: str = "nomic-embed-text"
    similarity_threshold: float = 0.7
    max_results: int = 10
    specialized_prompts: Dict[str, str] = {}
    vector_index_path: str
    is_active: bool = True

    model_config = {"from_attributes": True}


class DomainConfigManager:
    """Manages domain configurations"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self._cache: Dict[str, DomainSettings] = {}
        self._permissions_cache: Dict[str, Dict[str, List[str]]] = {}

    def get_domain_config(self, domain_name: str) -> Optional[DomainSettings]:
        """Get configuration for a specific domain"""
        if domain_name in self._cache:
            return self._cache[domain_name]
        
        config = self.db.query(DomainConfig).filter(
            DomainConfig.domain_name == domain_name,
            DomainConfig.is_active == True
        ).first()
        
        if config:
            domain_settings = DomainSettings.model_validate(config)
            self._cache[domain_name] = domain_settings
            return domain_settings
        
        return None

    def get_all_active_domains(self) -> List[DomainSettings]:
        """Get all active domain configurations"""
        configs = self.db.query(DomainConfig).filter(
            DomainConfig.is_active == True
        ).all()
        
        return [DomainSettings.model_validate(config) for config in configs]

    def get_user_accessible_domains(self, user_domains: List[str]) -> List[DomainSettings]:
        """Get domain configurations for domains user has access to"""
        configs = self.db.query(DomainConfig).filter(
            DomainConfig.domain_name.in_(user_domains),
            DomainConfig.is_active == True
        ).all()
        
        return [DomainSettings.model_validate(config) for config in configs]

    def get_domain_permissions(self, domain_name: str) -> Dict[str, List[str]]:
        """Get role permissions for a domain"""
        if domain_name in self._permissions_cache:
            return self._permissions_cache[domain_name]
        
        permissions = self.db.query(DomainPermission).filter(
            DomainPermission.domain_name == domain_name
        ).all()
        
        role_permissions = {}
        for perm in permissions:
            role_permissions[perm.role_name] = perm.permissions
        
        self._permissions_cache[domain_name] = role_permissions
        return role_permissions

    def check_user_domain_access(self, user_domains: List[str], 
                                user_roles: Dict[str, List[str]], 
                                domain: str, action: str = "read") -> bool:
        """Check if user has access to domain with specific action"""
        if domain not in user_domains:
            return False
        
        domain_permissions = self.get_domain_permissions(domain)
        user_domain_roles = user_roles.get(domain, [])
        
        for role in user_domain_roles:
            if role in domain_permissions:
                if action in domain_permissions[role]:
                    return True
        
        return False

    def create_domain(self, domain_settings: DomainSettings) -> DomainSettings:
        """Create a new domain configuration"""
        config = DomainConfig(**domain_settings.model_dump())
        self.db.add(config)
        self.db.commit()
        self.db.refresh(config)
        
        # Clear cache
        self._cache.pop(domain_settings.domain_name, None)
        
        return DomainSettings.model_validate(config)

    def update_domain(self, domain_name: str, updates: Dict) -> Optional[DomainSettings]:
        """Update domain configuration"""
        config = self.db.query(DomainConfig).filter(
            DomainConfig.domain_name == domain_name
        ).first()
        
        if not config:
            return None
        
        for key, value in updates.items():
            if hasattr(config, key):
                setattr(config, key, value)
        
        config.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(config)
        
        # Clear cache
        self._cache.pop(domain_name, None)
        
        return DomainSettings.model_validate(config)

    def delete_domain(self, domain_name: str) -> bool:
        """Soft delete a domain (set inactive)"""
        config = self.db.query(DomainConfig).filter(
            DomainConfig.domain_name == domain_name
        ).first()
        
        if not config:
            return False
        
        config.is_active = False
        config.updated_at = datetime.utcnow()
        self.db.commit()
        
        # Clear cache
        self._cache.pop(domain_name, None)
        
        return True

    def refresh_cache(self):
        """Clear configuration cache to force reload"""
        self._cache.clear()
        self._permissions_cache.clear() 