"""
Domain Access Control System
Manages user access to different knowledge domains with role-based permissions.
"""

from typing import Dict, List, Optional, Set
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

class DomainRole(Enum):
    """Available roles within a domain"""
    VIEWER = "viewer"           # Read-only access
    USER = "user"              # Standard user access
    CONTRIBUTOR = "contributor" # Can upload/modify content
    ADMIN = "admin"            # Full domain administration
    OWNER = "owner"            # Domain ownership

class Permission(Enum):
    """Granular permissions within domains"""
    READ = "read"
    WRITE = "write"
    DELETE = "delete"
    ADMIN = "admin"
    UPLOAD = "upload"
    CONFIGURE = "configure"
    AUDIT = "audit"

@dataclass
class DomainConfig:
    """Configuration for a knowledge domain"""
    name: str
    description: str
    enabled: bool = True
    public_access: bool = False
    required_roles: List[DomainRole] = None
    
    def __post_init__(self):
        if self.required_roles is None:
            self.required_roles = [DomainRole.USER]

class DomainAccessControl:
    """Enhanced domain access control with role-based permissions"""
    
    # Domain permission mappings
    ROLE_PERMISSIONS = {
        DomainRole.VIEWER: {Permission.READ},
        DomainRole.USER: {Permission.READ, Permission.UPLOAD},
        DomainRole.CONTRIBUTOR: {Permission.READ, Permission.WRITE, Permission.UPLOAD},
        DomainRole.ADMIN: {Permission.READ, Permission.WRITE, Permission.DELETE, 
                          Permission.UPLOAD, Permission.CONFIGURE, Permission.AUDIT},
        DomainRole.OWNER: {Permission.READ, Permission.WRITE, Permission.DELETE, 
                          Permission.UPLOAD, Permission.CONFIGURE, Permission.AUDIT, Permission.ADMIN}
    }
    
    # Default domain configurations
    DEFAULT_DOMAINS = {
        "general": DomainConfig("General", "General knowledge and documentation", public_access=True),
        "support": DomainConfig("Support", "Customer support and troubleshooting"),
        "sales": DomainConfig("Sales", "Sales materials and customer information"),
        "engineering": DomainConfig("Engineering", "Technical documentation and code"),
        "product": DomainConfig("Product", "Product specifications and roadmaps")
    }
    
    def __init__(self):
        self.domains = self.DEFAULT_DOMAINS.copy()
        
    def check_domain_access(self, user_domains: Dict[str, List[str]], 
                           domain: str, permission: Permission) -> bool:
        """
        Check if user has specific permission in domain
        
        Args:
            user_domains: Dict mapping domain names to user roles in that domain
            domain: Target domain name
            permission: Required permission
            
        Returns:
            bool: True if access granted
        """
        try:
            # Check if domain exists and is enabled
            if domain not in self.domains or not self.domains[domain].enabled:
                logger.warning(f"Access denied: Domain '{domain}' not found or disabled")
                return False
            
            domain_config = self.domains[domain]
            
            # Check public access for read operations
            if domain_config.public_access and permission == Permission.READ:
                return True
            
            # Check user roles in domain
            user_roles = user_domains.get(domain, [])
            if not user_roles:
                logger.info(f"Access denied: User has no roles in domain '{domain}'")
                return False
            
            # Check if any user role has required permission
            for role_str in user_roles:
                try:
                    role = DomainRole(role_str)
                    role_permissions = self.ROLE_PERMISSIONS.get(role, set())
                    if permission in role_permissions:
                        logger.debug(f"Access granted: Role '{role}' has permission '{permission}' in domain '{domain}'")
                        return True
                except ValueError:
                    logger.warning(f"Invalid role '{role_str}' for user in domain '{domain}'")
                    continue
            
            logger.info(f"Access denied: No sufficient permissions for '{permission}' in domain '{domain}'")
            return False
            
        except Exception as e:
            logger.error(f"Error checking domain access: {e}")
            return False
    
    def get_user_permissions(self, user_domains: Dict[str, List[str]], domain: str) -> Set[Permission]:
        """Get all permissions user has in a domain"""
        permissions = set()
        
        if domain not in self.domains:
            return permissions
        
        domain_config = self.domains[domain]
        
        # Add public read permission if applicable
        if domain_config.public_access:
            permissions.add(Permission.READ)
        
        # Add role-based permissions
        user_roles = user_domains.get(domain, [])
        for role_str in user_roles:
            try:
                role = DomainRole(role_str)
                role_permissions = self.ROLE_PERMISSIONS.get(role, set())
                permissions.update(role_permissions)
            except ValueError:
                continue
        
        return permissions
    
    def get_accessible_domains(self, user_domains: Dict[str, List[str]]) -> List[str]:
        """Get list of domains user can access"""
        accessible = []
        
        for domain_name, domain_config in self.domains.items():
            if not domain_config.enabled:
                continue
                
            # Check public access
            if domain_config.public_access:
                accessible.append(domain_name)
                continue
            
            # Check user roles
            if domain_name in user_domains and user_domains[domain_name]:
                accessible.append(domain_name)
        
        return accessible
    
    def add_domain(self, domain_name: str, config: DomainConfig) -> bool:
        """Add new domain configuration"""
        try:
            self.domains[domain_name] = config
            logger.info(f"Added domain '{domain_name}'")
            return True
        except Exception as e:
            logger.error(f"Error adding domain '{domain_name}': {e}")
            return False
    
    def update_domain(self, domain_name: str, config: DomainConfig) -> bool:
        """Update existing domain configuration"""
        try:
            if domain_name not in self.domains:
                logger.warning(f"Domain '{domain_name}' not found for update")
                return False
            
            self.domains[domain_name] = config
            logger.info(f"Updated domain '{domain_name}'")
            return True
        except Exception as e:
            logger.error(f"Error updating domain '{domain_name}': {e}")
            return False
    
    def remove_domain(self, domain_name: str) -> bool:
        """Remove domain (disable rather than delete)"""
        try:
            if domain_name not in self.domains:
                logger.warning(f"Domain '{domain_name}' not found for removal")
                return False
            
            self.domains[domain_name].enabled = False
            logger.info(f"Disabled domain '{domain_name}'")
            return True
        except Exception as e:
            logger.error(f"Error removing domain '{domain_name}': {e}")
            return False
    
    def validate_role_assignment(self, domain: str, role: str) -> bool:
        """Validate if role can be assigned to domain"""
        try:
            if domain not in self.domains:
                return False
            
            DomainRole(role)  # Validate role exists
            return True
        except ValueError:
            return False
    
    def get_domain_info(self, domain: str) -> Optional[Dict]:
        """Get domain configuration and metadata"""
        if domain not in self.domains:
            return None
        
        config = self.domains[domain]
        return {
            "name": config.name,
            "description": config.description,
            "enabled": config.enabled,
            "public_access": config.public_access,
            "required_roles": [role.value for role in config.required_roles],
            "available_roles": [role.value for role in DomainRole],
            "permissions": {
                role.value: [perm.value for perm in perms] 
                for role, perms in self.ROLE_PERMISSIONS.items()
            }
        } 