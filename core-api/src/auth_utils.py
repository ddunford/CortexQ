"""
Enhanced Authentication Utilities
Migrated from services/infrastructure/auth-service/src/auth_utils.py
Provides RBAC, JWT management, and permission checking
"""

import json
import uuid
import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

from jose import jwt, JWTError
import bcrypt
from sqlalchemy.orm import Session
from sqlalchemy import text
import redis

# Configuration - Read from environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24  # 24 hours
REFRESH_TOKEN_EXPIRE_DAYS = 30


class AuthUtils:
    """Enhanced authentication utilities with RBAC support"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against hash"""
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token with enhanced payload"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        })
        
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
        
        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "refresh"
        })
        
        encoded_jwt = jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload"""
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                return None
            
            # Check expiration
            if datetime.utcnow() > datetime.fromtimestamp(payload.get("exp", 0)):
                return None
            
            return payload
            
        except JWTError:
            return None
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate a short random session token for database storage"""
        import secrets
        return secrets.token_urlsafe(32)


class PermissionManager:
    """Role-based access control and permission management"""
    
    @staticmethod
    def get_user_roles(db: Session, user_id: str) -> List[str]:
        """Get user roles from database"""
        result = db.execute(
            text("""
                SELECT r.name 
                FROM roles r
                JOIN user_roles ur ON r.id = ur.role_id
                WHERE ur.user_id = :user_id
            """),
            {"user_id": user_id}
        )
        return [row.name for row in result.fetchall()]
    
    @staticmethod
    def get_user_permissions(db: Session, user_id: str) -> List[str]:
        """Get user permissions from database"""
        result = db.execute(
            text("""
                SELECT DISTINCT p.name
                FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                JOIN user_roles ur ON rp.role_id = ur.role_id
                WHERE ur.user_id = :user_id
            """),
            {"user_id": user_id}
        )
        return [row.name for row in result.fetchall()]
    
    @staticmethod
    def get_user_domains(db: Session, user_id: str) -> List[str]:
        """Get user accessible domains - simplified for current schema"""
        # For now, return default domains since domain_access table doesn't exist
        # In the future, this could be based on organization membership
        return ["general"]
    
    @staticmethod
    def has_permission(db: Session, user_id: str, permission: str) -> bool:
        """Check if user has specific permission"""
        permissions = PermissionManager.get_user_permissions(db, user_id)
        
        # Check for wildcard permissions
        if "*:*" in permissions:
            return True
        
        # Check for exact match
        if permission in permissions:
            return True
        
        # Check for resource wildcard (e.g., "files:*")
        resource, action = permission.split(":", 1) if ":" in permission else (permission, "*")
        resource_wildcard = f"{resource}:*"
        if resource_wildcard in permissions:
            return True
        
        return False
    
    @staticmethod
    def has_domain_access(db: Session, user_id: str, domain: str) -> bool:
        """Check if user has access to specific domain"""
        # Check if user has access to domain through organization membership
        # Handle both domain IDs and domain names for backwards compatibility
        if len(domain) == 36 and domain.count('-') == 4:  # Likely a UUID (domain ID)
            result = db.execute(
                text("""
                    SELECT 1
                    FROM organization_members om
                    JOIN organization_domains od ON om.organization_id = od.organization_id
                    WHERE om.user_id = :user_id 
                    AND od.id = :domain_id
                    AND om.is_active = true 
                    AND od.is_active = true
                    LIMIT 1
                """),
                {"user_id": user_id, "domain_id": domain}
            ).fetchone()
        else:
            # Legacy support for domain names
            result = db.execute(
                text("""
                    SELECT 1
                    FROM organization_members om
                    JOIN organization_domains od ON om.organization_id = od.organization_id
                    WHERE om.user_id = :user_id 
                    AND od.domain_name = :domain_name
                    AND om.is_active = true 
                    AND od.is_active = true
                    LIMIT 1
                """),
                {"user_id": user_id, "domain_name": domain}
            ).fetchone()
        
        return result is not None
    
    @staticmethod
    def has_role(user_roles: List[str], role_name: str) -> bool:
        """Check if user has specific role"""
        return role_name in user_roles
    
    @staticmethod
    def is_admin(user_roles: List[str]) -> bool:
        """Check if user is admin"""
        return "admin" in user_roles


class AuditLogger:
    """Enhanced audit logging functionality"""
    
    @staticmethod
    def log_event(
        db: Session,
        event_type: str,
        user_id: Optional[str] = None,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        description: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        severity: str = "info"
    ):
        """Log audit event to database"""
        # For now, just skip audit logging to avoid transaction conflicts
        # TODO: Implement proper audit logging with separate session
        try:
            print(f"AUDIT: {event_type} - {description} (user: {user_id})")
        except Exception:
            pass
    
    @staticmethod
    def log_authentication(
        db: Session,
        user_id: str,
        action: str,
        success: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None
    ):
        """Log authentication events"""
        AuditLogger.log_event(
            db=db,
            event_type="authentication",
            user_id=user_id,
            action=action,
            description=f"User {action} {'successful' if success else 'failed'}",
            event_data={
                "success": success,
                "details": details or {}
            },
            ip_address=ip_address,
            user_agent=user_agent,
            severity="info" if success else "warning"
        )
    
    @staticmethod
    def log_permission_check(
        db: Session,
        user_id: str,
        permission: str,
        resource: str,
        granted: bool,
        ip_address: Optional[str] = None
    ):
        """Log permission checks"""
        AuditLogger.log_event(
            db=db,
            event_type="permission_check",
            user_id=user_id,
            resource=resource,
            action=permission,
            description=f"Permission {permission} {'granted' if granted else 'denied'}",
            event_data={"permission": permission, "granted": granted},
            ip_address=ip_address,
            severity="info" if granted else "warning"
        )


class SessionManager:
    """Enhanced session management with Redis support"""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
    
    def create_session(
        self,
        db: Session,
        user_id: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> tuple[str, str]:
        """Create new user session with tokens"""
        session_id = str(uuid.uuid4())
        access_token = AuthUtils.create_access_token({"sub": user_id, "session_id": session_id})
        refresh_token = AuthUtils.create_refresh_token({"sub": user_id, "session_id": session_id})
        
        # Generate shorter session tokens for database storage
        session_token = AuthUtils.generate_session_token()  # Short random token
        refresh_session_token = AuthUtils.generate_session_token()  # Short random token
        
        # Store session in database with shorter tokens
        try:
            db.execute(
                text("""
                    INSERT INTO user_sessions (
                        id, user_id, session_token, refresh_token, ip_address,
                        user_agent, expires_at, created_at
                    ) VALUES (
                        :id, :user_id, :session_token, :refresh_token, :ip_address,
                        :user_agent, :expires_at, :created_at
                    )
                """),
                {
                    "id": session_id,
                    "user_id": user_id,
                    "session_token": session_token,  # Use short token
                    "refresh_token": refresh_session_token,  # Use short token
                    "ip_address": ip_address,
                    "user_agent": user_agent,
                    "expires_at": datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
                    "created_at": datetime.utcnow()
                }
            )
            db.commit()
        except Exception as e:
            db.rollback()
            raise e
        
        # Cache session data in Redis if available
        if self.redis_client:
            try:
                session_data = {
                    "user_id": user_id,
                    "ip_address": ip_address,
                    "created_at": datetime.utcnow().isoformat()
                }
                self.redis_client.setex(
                    f"session:{session_id}",
                    timedelta(hours=24),
                    json.dumps(session_data)
                )
            except Exception:
                pass  # Don't fail if Redis is unavailable
        
        return access_token, refresh_token
    
    def invalidate_session(self, db: Session, session_id: str):
        """Invalidate user session"""
        # Remove from database
        db.execute(
            text("UPDATE user_sessions SET is_active = false WHERE id = :session_id"),
            {"session_id": session_id}
        )
        db.commit()
        
        # Remove from Redis
        if self.redis_client:
            try:
                self.redis_client.delete(f"session:{session_id}")
            except Exception:
                pass
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session data"""
        if self.redis_client:
            try:
                session_data = self.redis_client.get(f"session:{session_id}")
                if session_data:
                    return json.loads(session_data)
            except Exception:
                pass
        
        return None 