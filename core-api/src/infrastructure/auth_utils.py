"""
Authentication Utilities
Handles password hashing, JWT tokens, and permission checking
"""

import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from config import settings
from models import User, Role, UserSession, AuditLog

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class AuthUtils:
    """Authentication utilities"""
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)
    
    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)
    
    @staticmethod
    def validate_password_strength(password: str) -> tuple[bool, List[str]]:
        """Validate password strength"""
        errors = []
        
        if len(password) < settings.PASSWORD_MIN_LENGTH:
            errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long")
        
        if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
            errors.append("Password must contain at least one uppercase letter")
        
        if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
            errors.append("Password must contain at least one lowercase letter")
        
        if settings.PASSWORD_REQUIRE_NUMBERS and not any(c.isdigit() for c in password):
            errors.append("Password must contain at least one number")
        
        if settings.PASSWORD_REQUIRE_SPECIAL and not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in password):
            errors.append("Password must contain at least one special character")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
        
        to_encode.update({"exp": expire, "type": "access"})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def create_refresh_token(data: Dict[str, Any]) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return encoded_jwt
    
    @staticmethod
    def verify_token(token: str, token_type: str = "access") -> Optional[Dict[str, Any]]:
        """Verify and decode JWT token"""
        try:
            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            
            # Check token type
            if payload.get("type") != token_type:
                return None
            
            # Check expiration
            exp = payload.get("exp")
            if exp and datetime.utcfromtimestamp(exp) < datetime.utcnow():
                return None
            
            return payload
        except JWTError:
            return None
    
    @staticmethod
    def generate_session_token() -> str:
        """Generate secure session token"""
        return secrets.token_urlsafe(32)


class PermissionManager:
    """Permission and role management"""
    
    @staticmethod
    def get_user_permissions(user: User) -> List[str]:
        """Get all permissions for a user"""
        permissions = set()
        
        for role in user.roles:
            if role.is_active:
                permissions.update(role.permissions)
        
        return list(permissions)
    
    @staticmethod
    def get_user_domains(user: User) -> List[str]:
        """Get all accessible domains for a user"""
        domains = set()
        
        for role in user.roles:
            if role.is_active:
                domains.update(role.domain_access)
        
        return list(domains)
    
    @staticmethod
    def check_permission(user: User, resource: str, action: str, domain: Optional[str] = None) -> tuple[bool, str]:
        """Check if user has permission for resource/action"""
        
        # Superuser has all permissions
        if user.is_superuser:
            return True, "Superuser access"
        
        # Check if user is active
        if not user.is_active:
            return False, "User account is inactive"
        
        # Get user permissions
        user_permissions = PermissionManager.get_user_permissions(user)
        user_domains = PermissionManager.get_user_domains(user)
        
        # Check domain access if specified
        if domain and domain not in user_domains:
            return False, f"No access to domain: {domain}"
        
        # Build required permission string
        required_permission = f"{resource}:{action}"
        
        # Check specific permission
        if required_permission in user_permissions:
            return True, "Direct permission granted"
        
        # Check wildcard permissions
        resource_wildcard = f"{resource}:*"
        if resource_wildcard in user_permissions:
            return True, "Resource wildcard permission granted"
        
        action_wildcard = f"*:{action}"
        if action_wildcard in user_permissions:
            return True, "Action wildcard permission granted"
        
        full_wildcard = "*:*"
        if full_wildcard in user_permissions:
            return True, "Full wildcard permission granted"
        
        return False, f"Missing permission: {required_permission}"
    
    @staticmethod
    def has_role(user: User, role_name: str) -> bool:
        """Check if user has specific role"""
        return any(role.name == role_name and role.is_active for role in user.roles)


class AuditLogger:
    """Audit logging utilities"""
    
    @staticmethod
    def log_event(
        db: Session,
        user_id: Optional[str],
        event_type: str,
        event_description: str,
        resource: Optional[str] = None,
        action: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Log an audit event"""
        
        audit_log = AuditLog(
            user_id=user_id,
            event_type=event_type,
            event_description=event_description,
            resource=resource,
            action=action,
            ip_address=ip_address,
            user_agent=user_agent,
            request_id=request_id,
            metadata=metadata or {}
        )
        
        db.add(audit_log)
        db.commit()
    
    @staticmethod
    def log_login(db: Session, user: User, ip_address: str, user_agent: str, success: bool):
        """Log login attempt"""
        event_type = "login_success" if success else "login_failure"
        description = f"User {user.email} login {'successful' if success else 'failed'}"
        
        AuditLogger.log_event(
            db=db,
            user_id=str(user.id) if success else None,
            event_type=event_type,
            event_description=description,
            resource="auth",
            action="login",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"email": user.email}
        )
    
    @staticmethod
    def log_logout(db: Session, user: User, ip_address: str, user_agent: str):
        """Log logout"""
        AuditLogger.log_event(
            db=db,
            user_id=str(user.id),
            event_type="logout",
            event_description=f"User {user.email} logged out",
            resource="auth",
            action="logout",
            ip_address=ip_address,
            user_agent=user_agent
        )
    
    @staticmethod
    def log_permission_check(
        db: Session, 
        user: User, 
        resource: str, 
        action: str, 
        allowed: bool,
        ip_address: str
    ):
        """Log permission check"""
        event_type = "permission_granted" if allowed else "permission_denied"
        description = f"Permission check for {user.email}: {resource}:{action} - {'Allowed' if allowed else 'Denied'}"
        
        AuditLogger.log_event(
            db=db,
            user_id=str(user.id),
            event_type=event_type,
            event_description=description,
            resource=resource,
            action=action,
            ip_address=ip_address,
            metadata={"permission_result": allowed}
        ) 