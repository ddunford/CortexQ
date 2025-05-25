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
        
        # Get user from database with permissions
        user_data = AuthUtils.get_user_with_permissions(db, user_id)
        if not user_data:
            logger.warning(f"User {user_id} not found in database")
            raise HTTPException(status_code=401, detail="User not found")
        
        if not user_data.get("is_active", False):
            logger.warning(f"User {user_id} is not active")
            raise HTTPException(status_code=401, detail="User account is disabled")
        
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