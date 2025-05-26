"""
Authentication dependency functions
"""

import logging
from typing import Dict, Any
from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from auth_utils import AuthUtils, PermissionManager
from .database_dependencies import get_db

logger = logging.getLogger(__name__)
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency to get current authenticated user
    Validates JWT token and returns user information
    """
    try:
        token = credentials.credentials
        
        # Verify the token
        payload = AuthUtils.verify_token(token, "access")
        if not payload:
            logger.warning("Invalid token provided")
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Token missing user ID")
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Get user from database
        from sqlalchemy import text
        user_result = db.execute(
            text("""
                SELECT id, username, email, full_name, is_active, created_at
                FROM users WHERE id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()
        
        if not user_result:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user_result.is_active:
            logger.warning(f"User {user_id} is not active")
            raise HTTPException(status_code=401, detail="User account is disabled")
        
        # Get user permissions and roles
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        user_data = {
            "id": str(user_result.id),
            "username": user_result.username,
            "email": user_result.email,
            "full_name": user_result.full_name,
            "is_active": user_result.is_active,
            "roles": roles,
            "permissions": permissions,
            "domains": domains
        }
        
        return user_data
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_current_user: {str(e)}")
        raise HTTPException(status_code=401, detail="Authentication failed")


def require_permission(permission: str):
    """Dependency factory to require specific permission"""
    def permission_dependency(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        user_id = current_user["id"]
        has_permission = PermissionManager.has_permission(db, user_id, permission)
        
        if not has_permission:
            logger.warning(f"User {user_id} lacks permission: {permission}")
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required"
            )
        
        return current_user
    
    return permission_dependency


def require_admin():
    """Dependency to require admin role"""
    def admin_dependency(current_user: dict = Depends(get_current_user)):
        user_roles = current_user.get("roles", [])
        
        if "admin" not in user_roles:
            logger.warning(f"User {current_user['id']} attempted admin action without admin role")
            raise HTTPException(
                status_code=403,
                detail="Admin access required"
            )
        
        return current_user
    
    return admin_dependency


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Dependency to get current user if authenticated, None otherwise
    Does not raise exceptions for missing/invalid tokens
    """
    try:
        if not credentials:
            return None
            
        token = credentials.credentials
        
        # Verify the token
        payload = AuthUtils.verify_token(token, "access")
        if not payload:
            return None
        
        user_id = payload.get("sub")
        if not user_id:
            return None
        
        # Get user from database
        from sqlalchemy import text
        user_result = db.execute(
            text("""
                SELECT id, username, email, full_name, is_active, created_at
                FROM users WHERE id = :user_id
            """),
            {"user_id": user_id}
        ).fetchone()
        
        if not user_result or not user_result.is_active:
            return None
        
        # Get user permissions and roles
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        user_data = {
            "id": str(user_result.id),
            "username": user_result.username,
            "email": user_result.email,
            "full_name": user_result.full_name,
            "is_active": user_result.is_active,
            "roles": roles,
            "permissions": permissions,
            "domains": domains
        }
        
        return user_data
        
    except Exception:
        # Silently return None for any errors
        return None


async def verify_organization_access(
    user: Dict[str, Any],
    organization_id: str,
    db: Session
) -> bool:
    """
    Verify that a user has access to a specific organization
    
    Args:
        user: Current authenticated user
        organization_id: Organization ID to check access for
        db: Database session
    
    Returns:
        bool: True if user has access, False otherwise
    """
    try:
        # Check if user is a member of the organization
        from sqlalchemy import text
        membership_result = db.execute(
            text("""
                SELECT om.id, om.role, o.is_active
                FROM organization_members om
                JOIN organizations o ON om.organization_id = o.id
                WHERE om.user_id = :user_id 
                AND om.organization_id = :organization_id
                AND om.is_active = true
                AND o.is_active = true
            """),
            {
                "user_id": user["id"],
                "organization_id": organization_id
            }
        ).fetchone()
        
        return membership_result is not None
        
    except Exception as e:
        logger.error(f"Error verifying organization access: {e}")
        return False 