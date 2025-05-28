"""
Authentication and User Management Routes
Extracted from main.py for better code organization
"""

import uuid
import json
import logging
from datetime import datetime
from typing import List
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy import text

import sys
import os
# Add the parent directory to the path
parent_dir = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, parent_dir)

from models import (
    LoginRequest, LoginResponse, UserCreate, UserResponse, 
    PermissionCheck, RoleCreate
)
from dependencies import get_db, get_current_user, require_permission, require_admin
from dependencies.auth_dependencies import security
from auth_utils import AuthUtils, PermissionManager, AuditLogger, SessionManager

# Initialize router
router = APIRouter(tags=["authentication"])

# Initialize session manager (will be set by main app)
session_manager = None

logger = logging.getLogger(__name__)


def set_session_manager(sm):
    """Set the session manager instance"""
    global session_manager
    session_manager = sm


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    """Enhanced login with RBAC and audit logging"""
    try:
        # Validate input
        if not request.username and not request.email:
            raise HTTPException(status_code=400, detail="Username or email is required")
        
        # Get user from database (support both username and email login)
        if request.email:
            result = db.execute(
                text("SELECT id, username, email, full_name, password_hash, is_active FROM users WHERE email = :email"),
                {"email": request.email}
            )
        else:
            result = db.execute(
                text("SELECT id, username, email, full_name, password_hash, is_active FROM users WHERE username = :username"),
                {"username": request.username}
            )
        user = result.fetchone()
        
        if not user or not user.is_active:
            # Log failed attempt
            if user:
                AuditLogger.log_authentication(
                    db, str(user.id), "login", False, 
                    details={"reason": "inactive_account"}
                )
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not AuthUtils.verify_password(request.password, user.password_hash):
            AuditLogger.log_authentication(
                db, str(user.id), "login", False,
                details={"reason": "invalid_password"}
            )
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Get user roles, permissions, and domains from database
        user_id = str(user.id)
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        # If user has no roles, assign default user role
        if not roles:
            # Check if default user role exists, if not create it
            default_role = db.execute(
                text("SELECT id FROM roles WHERE name = 'user'")
            ).fetchone()
            
            if default_role:
                # Assign user role
                db.execute(
                    text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                        ON CONFLICT DO NOTHING
                    """),
                    {"user_id": user_id, "role_id": str(default_role.id)}
                )
                db.commit()
                
                # Refresh roles and permissions
                roles = PermissionManager.get_user_roles(db, user_id)
                permissions = PermissionManager.get_user_permissions(db, user_id)
        
        # Create session and tokens
        access_token, refresh_token = session_manager.create_session(
            db, user_id
        )
        
        # Log successful login
        AuditLogger.log_authentication(
            db, user_id, "login", True,
            details={"roles": roles, "domains": domains}
        )
        
        # Update login statistics
        db.execute(
            text("""
                UPDATE users 
                SET last_login = :now, login_count = login_count + 1, failed_login_attempts = 0
                WHERE id = :user_id
            """),
            {"now": datetime.utcnow(), "user_id": user_id}
        )
        db.commit()
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user={
                "id": user_id,
                "username": user.username,
                "email": user.email,
                "full_name": user.full_name,
                "roles": roles,
                "permissions": permissions,
                "domains": domains
            }
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")


@router.post("/logout")
async def logout(
    current_user: dict = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Logout and invalidate session"""
    try:
        # Extract session ID from token
        payload = AuthUtils.verify_token(credentials.credentials, "access")
        session_id = payload.get("session_id")
        
        if session_id:
            session_manager.invalidate_session(db, session_id)
        
        # Log logout
        AuditLogger.log_authentication(
            db, current_user["id"], "logout", True
        )
        
        return {"message": "Logged out successfully"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user (public endpoint) - Email as primary identifier"""
    try:
        # Check if user already exists (email is both username and email)
        existing_user = db.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": user_data.email}
        ).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="User with this email already exists")
        
        # Hash password
        password_hash = AuthUtils.hash_password(user_data.password)
        
        # Create user (use email as both username and email for enterprise compatibility)
        user_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO users (id, username, email, full_name, password_hash, is_active, created_at)
                VALUES (:id, :username, :email, :full_name, :password_hash, :is_active, :created_at)
            """),
            {
                "id": user_id,
                "username": user_data.email,  # Use email as username
                "email": user_data.email,
                "full_name": user_data.full_name,
                "password_hash": password_hash,
                "is_active": True,  # Explicitly set user as active
                "created_at": datetime.utcnow()
            }
        )
        
        # Assign admin role to organization owners, user role to others
        default_roles = user_data.roles if user_data.roles else ["admin"]  # Organization owners get admin by default
        for role_name in default_roles:
            role_result = db.execute(
                text("SELECT id FROM roles WHERE name = :name"),
                {"name": role_name}
            )
            role = role_result.fetchone()
            if role:
                db.execute(
                    text("""
                        INSERT INTO user_roles (user_id, role_id, assigned_at)
                        VALUES (:user_id, :role_id, :assigned_at)
                    """),
                    {
                        "user_id": user_id,
                        "role_id": str(role.id),
                        "assigned_at": datetime.utcnow()
                    }
                )
            else:
                logger.warning(f"Role '{role_name}' not found in database")
        
        # Create default organization for new user
        org_id = str(uuid.uuid4())
        org_name = f"{user_data.full_name or user_data.email.split('@')[0]}'s Organization"
        org_slug = f"org-{int(datetime.utcnow().timestamp())}"
        
        # Set default limits for basic tier
        tier_limits = {
            "basic": {"max_users": 10, "max_storage_gb": 10, "max_domains": 3},
            "professional": {"max_users": 50, "max_storage_gb": 100, "max_domains": 10},
            "enterprise": {"max_users": 1000, "max_storage_gb": 1000, "max_domains": 50}
        }
        limits = tier_limits["basic"]
        
        db.execute(
            text("""
                INSERT INTO organizations (
                    id, name, slug, description, logo_url, website, industry,
                    size_category, subscription_tier, max_users, max_storage_gb, max_domains,
                    is_active, created_at
                ) VALUES (
                    :id, :name, :slug, :description, :logo_url, :website, :industry,
                    :size_category, :subscription_tier, :max_users, :max_storage_gb, :max_domains,
                    :is_active, :created_at
                )
            """),
            {
                "id": org_id,
                "name": org_name,
                "slug": org_slug,
                "description": f"Personal workspace for {user_data.email}",
                "logo_url": None,
                "website": None,
                "industry": None,
                "size_category": "small",
                "subscription_tier": "basic",
                "max_users": limits["max_users"],
                "max_storage_gb": limits["max_storage_gb"],
                "max_domains": limits["max_domains"],
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        )
        
        # Add user as owner of the organization
        member_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_members (id, user_id, organization_id, role, is_active, joined_at)
                VALUES (:id, :user_id, :organization_id, :role, :is_active, :joined_at)
            """),
            {
                "id": member_id,
                "user_id": user_id,
                "organization_id": org_id,
                "role": "owner",
                "is_active": True,
                "joined_at": datetime.utcnow()
            }
        )
        
        # Create default domain for the organization
        domain_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_domains (
                    id, organization_id, domain_name, display_name, description,
                    icon, color, created_by, is_active, created_at
                ) VALUES (
                    :id, :organization_id, :domain_name, :display_name, :description,
                    :icon, :color, :created_by, :is_active, :created_at
                )
            """),
            {
                "id": domain_id,
                "organization_id": org_id,
                "domain_name": "general",
                "display_name": "Knowledge Base",
                "description": "Main knowledge base for documents and data sources",
                "icon": "globe",
                "color": "blue",
                "created_by": user_id,
                "is_active": True,
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Get user data for response from database
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        # Log user registration
        AuditLogger.log_event(
            db, "user_registration", user_id, "users", "create",
            f"User {user_data.email} registered with organization {org_name}",
            {"roles": roles, "organization_id": org_id, "domain_id": domain_id}
        )
        
        return UserResponse(
            id=user_id,
            username=user_data.email,  # Return email as username for consistency
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=True,
            roles=roles,
            permissions=permissions,
            domains=domains
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Registration failed: {str(e)}")


@router.post("/check-permission")
async def check_permission(
    request: PermissionCheck,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check if user has specific permission"""
    has_perm = PermissionManager.has_permission(db, current_user["id"], request.permission)
    
    AuditLogger.log_permission_check(
        db, current_user["id"], request.permission, 
        request.resource or "general", has_perm
    )
    
    return {
        "user_id": current_user["id"],
        "permission": request.permission,
        "granted": has_perm,
        "resource": request.resource
    }


@router.post("/debug/fix-organization-membership")
async def fix_organization_membership(
    current_user: dict = Depends(require_permission("admin:access")),
    db: Session = Depends(get_db)
):
    """Fix users without organization membership (Admin only)"""
    try:
        # Get all users without organization membership
        users_without_org = db.execute(
            text("""
                SELECT u.id, u.email, u.full_name 
                FROM users u 
                LEFT JOIN organization_members om ON u.id = om.user_id AND om.is_active = true
                WHERE om.user_id IS NULL
            """)
        ).fetchall()
        
        if not users_without_org:
            return {"message": "All users already have organization membership", "fixed_count": 0}
        
        fixed_users = []
        
        for user in users_without_org:
            # Create organization for this user
            org_id = str(uuid.uuid4())
            org_name = f"{user.full_name or user.email.split('@')[0]}'s Organization"
            org_slug = f"org-{int(datetime.utcnow().timestamp())}-{user.id[:8]}"
            
            # Set default limits for basic tier
            limits = {"max_users": 10, "max_storage_gb": 10, "max_domains": 3}
            
            # Create organization
            db.execute(
                text("""
                    INSERT INTO organizations (
                        id, name, slug, description, logo_url, website, industry,
                        size_category, subscription_tier, max_users, max_storage_gb, max_domains,
                        is_active, created_at
                    ) VALUES (
                        :id, :name, :slug, :description, :logo_url, :website, :industry,
                        :size_category, :subscription_tier, :max_users, :max_storage_gb, :max_domains,
                        :is_active, :created_at
                    )
                """),
                {
                    "id": org_id,
                    "name": org_name,
                    "slug": org_slug,
                    "description": f"Personal workspace for {user.email}",
                    "logo_url": None,
                    "website": None,
                    "industry": None,
                    "size_category": "small",
                    "subscription_tier": "basic",
                    "max_users": limits["max_users"],
                    "max_storage_gb": limits["max_storage_gb"],
                    "max_domains": limits["max_domains"],
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Add user as owner of the organization
            member_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_members (
                        id, organization_id, user_id, role, joined_at, is_active
                    ) VALUES (
                        :id, :org_id, :user_id, 'owner', :joined_at, :is_active
                    )
                """),
                {
                    "id": member_id,
                    "org_id": org_id,
                    "user_id": str(user.id),
                    "joined_at": datetime.utcnow(),
                    "is_active": True
                }
            )
            
            # Create default domain for the organization
            domain_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO organization_domains (
                        id, organization_id, domain_name, display_name, description,
                        icon, color, created_by, is_active, created_at
                    ) VALUES (
                        :id, :organization_id, :domain_name, :display_name, :description,
                        :icon, :color, :created_by, :is_active, :created_at
                    )
                """),
                {
                    "id": domain_id,
                    "organization_id": org_id,
                    "domain_name": "general",
                    "display_name": "Knowledge Base",
                    "description": "Main knowledge base for documents and data sources",
                    "icon": "globe",
                    "color": "blue",
                    "created_by": str(user.id),
                    "is_active": True,
                    "created_at": datetime.utcnow()
                }
            )
            
            fixed_users.append({
                "user_email": user.email,
                "organization_id": org_id,
                "organization_name": org_name,
                "domain_id": domain_id
            })
        
        db.commit()
        
        # Log the fix
        AuditLogger.log_event(
            db, "organization_membership_fix", current_user["id"], "organization_members", "create",
            f"Fixed organization membership for {len(fixed_users)} users",
            {"fixed_users": fixed_users}
        )
        
        return {
            "message": f"Successfully fixed organization membership for {len(fixed_users)} users",
            "fixed_count": len(fixed_users),
            "fixed_users": fixed_users
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to fix organization membership: {str(e)}")


# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

# Create a separate router for user management
user_router = APIRouter(tags=["user-management"])


@user_router.post("", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: dict = Depends(require_permission("users:create")),
    db: Session = Depends(get_db)
):
    """Create new user with roles"""
    try:
        # Hash password
        password_hash = AuthUtils.hash_password(user_data.password)
        
        # Create user
        user_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO users (id, username, email, full_name, password_hash, created_at)
                VALUES (:id, :username, :email, :full_name, :password_hash, :created_at)
            """),
            {
                "id": user_id,
                "username": user_data.email,  # Use email as username
                "email": user_data.email,
                "full_name": user_data.full_name,
                "password_hash": password_hash,
                "created_at": datetime.utcnow()
            }
        )
        
        # Assign roles
        for role_name in user_data.roles:
            role_result = db.execute(
                text("SELECT id FROM roles WHERE name = :name"),
                {"name": role_name}
            )
            role = role_result.fetchone()
            if role:
                db.execute(
                    text("""
                        INSERT INTO user_roles (user_id, role_id)
                        VALUES (:user_id, :role_id)
                    """),
                    {
                        "user_id": user_id,
                        "role_id": str(role.id)
                    }
                )
        
        db.commit()
        
        # Get user data for response
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        # Log user creation
        AuditLogger.log_event(
            db, "user_creation", current_user["id"], "users", "create",
            f"Created user {user_data.email}",
            {"new_user_id": user_id, "roles": roles}
        )
        
        return UserResponse(
            id=user_id,
            username=user_data.email,
            email=user_data.email,
            full_name=user_data.full_name,
            is_active=True,
            roles=roles,
            permissions=permissions,
            domains=domains
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")


@user_router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current user information"""
    return UserResponse(
        id=current_user["id"],
        username=current_user["username"],
        email=current_user["email"],
        full_name=current_user["full_name"],
        is_active=current_user["is_active"],
        roles=current_user["roles"],
        permissions=current_user["permissions"],
        domains=current_user["domains"]
    )


@user_router.put("/me", response_model=UserResponse)
async def update_user_profile(
    profile_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    try:
        # Build update query dynamically based on provided fields
        update_fields = []
        params = {"user_id": current_user["id"], "updated_at": datetime.utcnow()}
        
        if "full_name" in profile_data:
            update_fields.append("full_name = :full_name")
            params["full_name"] = profile_data["full_name"]
        
        if "email" in profile_data:
            # Check if email is already taken
            existing = db.execute(
                text("SELECT id FROM users WHERE email = :email AND id != :user_id"),
                {"email": profile_data["email"], "user_id": current_user["id"]}
            ).fetchone()
            if existing:
                raise HTTPException(status_code=400, detail="Email already in use")
            
            update_fields.append("email = :email")
            params["email"] = profile_data["email"]
        
        if update_fields:
            update_query = f"""
                UPDATE users 
                SET {', '.join(update_fields)}, updated_at = :updated_at
                WHERE id = :user_id
            """
            db.execute(text(update_query), params)
            db.commit()
        
        # Get updated user data
        user_result = db.execute(
            text("""
                SELECT id, username, email, full_name, is_active, created_at
                FROM users WHERE id = :user_id
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        roles = PermissionManager.get_user_roles(db, current_user["id"])
        permissions = PermissionManager.get_user_permissions(db, current_user["id"])
        domains = PermissionManager.get_user_domains(db, current_user["id"])
        
        # Log profile update
        AuditLogger.log_event(
            db, "profile_update", current_user["id"], "users", "update",
            f"Updated profile for {user_result.email}",
            {"updated_fields": list(profile_data.keys())}
        )
        
        return UserResponse(
            id=str(user_result.id),
            username=user_result.username,
            email=user_result.email,
            full_name=user_result.full_name,
            is_active=user_result.is_active,
            roles=roles,
            permissions=permissions,
            domains=domains
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update profile: {str(e)}")


@user_router.put("/me/password")
async def change_user_password(
    password_data: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current user's password"""
    try:
        current_password = password_data.get("current_password")
        new_password = password_data.get("new_password")
        
        if not current_password or not new_password:
            raise HTTPException(status_code=400, detail="Current and new passwords are required")
        
        # Get current password hash
        user_result = db.execute(
            text("SELECT password_hash FROM users WHERE id = :user_id"),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        # Verify current password
        if not AuthUtils.verify_password(current_password, user_result.password_hash):
            raise HTTPException(status_code=400, detail="Current password is incorrect")
        
        # Hash new password
        new_password_hash = AuthUtils.hash_password(new_password)
        
        # Update password
        db.execute(
            text("""
                UPDATE users 
                SET password_hash = :password_hash, updated_at = :updated_at
                WHERE id = :user_id
            """),
            {
                "password_hash": new_password_hash,
                "updated_at": datetime.utcnow(),
                "user_id": current_user["id"]
            }
        )
        
        db.commit()
        
        # Log password change
        AuditLogger.log_event(
            db, "password_change", current_user["id"], "users", "update",
            f"Password changed for user {current_user['email']}",
            {}
        )
        
        return {"message": "Password updated successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to change password: {str(e)}")


# ============================================================================
# ROLE & PERMISSION MANAGEMENT
# ============================================================================

# Create a separate router for role management
role_router = APIRouter(tags=["role-management"])


@role_router.get("")
async def list_roles(
    current_user: dict = Depends(require_permission("roles:read")),
    db: Session = Depends(get_db)
):
    """List all roles"""
    result = db.execute(
        text("SELECT id, name, description, permissions, domain_access, is_active FROM roles ORDER BY name")
    )
    
    return [
        {
            "id": str(row.id),
            "name": row.name,
            "description": row.description,
            "permissions": json.loads(row.permissions) if row.permissions else [],
            "domain_access": json.loads(row.domain_access) if row.domain_access else [],
            "is_active": row.is_active
        }
        for row in result.fetchall()
    ]


@role_router.post("")
async def create_role(
    role_data: RoleCreate,
    current_user: dict = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Create new role"""
    try:
        role_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO roles (id, name, description, permissions, domain_access, created_at)
                VALUES (:id, :name, :description, :permissions, :domain_access, :created_at)
            """),
            {
                "id": role_id,
                "name": role_data.name,
                "description": role_data.description,
                "permissions": json.dumps(role_data.permissions),
                "domain_access": json.dumps(role_data.domain_access),
                "created_at": datetime.utcnow()
            }
        )
        db.commit()
        
        AuditLogger.log_event(
            db, "role_creation", current_user["id"], "roles", "create",
            f"Created role {role_data.name}",
            {"role_id": role_id, "permissions": role_data.permissions}
        )
        
        return {"id": role_id, "message": "Role created successfully"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create role: {str(e)}")


# Export all routers
__all__ = ["router", "user_router", "role_router"] 