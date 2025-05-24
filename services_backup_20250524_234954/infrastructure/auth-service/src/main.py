"""
Authentication Service - Main Application
Provides JWT-based authentication, authorization, and user management
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any

import uvicorn
from fastapi import FastAPI, HTTPException, Depends, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import IntegrityError
import redis
import logging

from config import settings
from models import (
    Base, User, Role, UserSession, AuditLog, UserRole,
    UserCreate, UserUpdate, UserResponse, LoginRequest, LoginResponse,
    TokenRefreshRequest, TokenResponse, PasswordChangeRequest, PasswordResetRequest,
    RoleCreate, RoleUpdate, RoleResponse, PermissionCheck, PermissionResponse,
    UserStats, HealthResponse
)
from auth_utils import AuthUtils, PermissionManager, AuditLogger

# Configure logging
logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper()))
logger = logging.getLogger(__name__)

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
try:
    redis_client = redis.from_url(settings.REDIS_URL)
    redis_client.ping()
    logger.info("Connected to Redis")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

# Security
security = HTTPBearer()

# FastAPI app
app = FastAPI(
    title="Authentication Service",
    description="JWT-based authentication and authorization service",
    version=settings.SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database dependency
def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Authentication dependency
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Get current authenticated user"""
    
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Verify token
        payload = AuthUtils.verify_token(credentials.credentials, "access")
        if payload is None:
            raise credentials_exception
        
        user_id = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        # Get user from database
        user = db.query(User).filter(User.id == user_id).first()
        if user is None:
            raise credentials_exception
        
        # Check if user is active
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account is inactive"
            )
        
        return user
        
    except Exception as e:
        logger.error(f"Authentication error: {e}")
        raise credentials_exception

# Admin user dependency
async def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    """Require admin user"""
    if not PermissionManager.has_role(current_user, "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user

# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize database and create default admin user"""
    
    # Create tables
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")
    
    # Create default roles
    db = SessionLocal()
    try:
        # Check if roles exist
        existing_roles = db.query(Role).count()
        if existing_roles == 0:
            logger.info("Creating default roles...")
            
            # Create default roles
            roles_data = [
                {
                    "name": "admin",
                    "description": "System Administrator",
                    "permissions": ["*:*"],
                    "domain_access": ["general", "support", "sales", "engineering", "product"]
                },
                {
                    "name": "support",
                    "description": "Support Team Member",
                    "permissions": ["chat:read", "chat:write", "files:read", "search:read"],
                    "domain_access": ["general", "support"]
                },
                {
                    "name": "sales",
                    "description": "Sales Team Member",
                    "permissions": ["chat:read", "chat:write", "files:read", "search:read"],
                    "domain_access": ["general", "sales"]
                },
                {
                    "name": "engineering",
                    "description": "Engineering Team Member",
                    "permissions": ["chat:read", "chat:write", "files:read", "files:write", "search:read"],
                    "domain_access": ["general", "engineering"]
                },
                {
                    "name": "product",
                    "description": "Product Team Member",
                    "permissions": ["chat:read", "chat:write", "files:read", "search:read"],
                    "domain_access": ["general", "product"]
                },
                {
                    "name": "user",
                    "description": "Regular User",
                    "permissions": ["chat:read", "search:read"],
                    "domain_access": ["general"]
                }
            ]
            
            for role_data in roles_data:
                role = Role(**role_data)
                db.add(role)
            
            db.commit()
            logger.info("Default roles created")
        
        # Create default admin user
        admin_user = db.query(User).filter(User.email == settings.DEFAULT_ADMIN_EMAIL).first()
        if not admin_user:
            logger.info("Creating default admin user...")
            
            # Get admin role
            admin_role = db.query(Role).filter(Role.name == "admin").first()
            
            admin_user = User(
                email=settings.DEFAULT_ADMIN_EMAIL,
                username="admin",
                full_name="System Administrator",
                hashed_password=AuthUtils.get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                is_active=True,
                is_verified=True,
                is_superuser=True
            )
            
            if admin_role:
                admin_user.roles.append(admin_role)
            
            db.add(admin_user)
            db.commit()
            logger.info("Default admin user created")
            
    except Exception as e:
        logger.error(f"Startup error: {e}")
        db.rollback()
    finally:
        db.close()

# Health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    
    # Check database
    db_healthy = True
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
    except Exception:
        db_healthy = False
    
    # Check cache
    cache_healthy = True
    if redis_client:
        try:
            redis_client.ping()
        except Exception:
            cache_healthy = False
    else:
        cache_healthy = False
    
    return HealthResponse(
        status="healthy" if db_healthy and cache_healthy else "degraded",
        service="auth-service",
        version=settings.SERVICE_VERSION,
        timestamp=datetime.utcnow(),
        database_healthy=db_healthy,
        cache_healthy=cache_healthy
    )

# Authentication endpoints
@app.post("/auth/login", response_model=LoginResponse)
async def login(
    login_data: LoginRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """User login"""
    
    # Get user
    user = db.query(User).filter(User.email == login_data.email).first()
    
    if not user or not AuthUtils.verify_password(login_data.password, user.hashed_password):
        # Log failed login attempt
        if user:
            AuditLogger.log_login(
                db, user, request.client.host, 
                request.headers.get("user-agent", ""), False
            )
        
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    # Create tokens
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    if login_data.remember_me:
        access_token_expires = timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    access_token = AuthUtils.create_access_token(
        data={"sub": str(user.id)}, 
        expires_delta=access_token_expires
    )
    refresh_token = AuthUtils.create_refresh_token(data={"sub": str(user.id)})
    
    # Create session
    session = UserSession(
        user_id=user.id,
        session_token=AuthUtils.generate_session_token(),  # Use unique session token
        refresh_token=refresh_token,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent", ""),
        expires_at=datetime.utcnow() + access_token_expires
    )
    db.add(session)
    
    # Update user login info
    user.last_login = datetime.utcnow()
    user.login_count = str(int(user.login_count) + 1)
    user.failed_login_attempts = "0"
    
    db.commit()
    
    # Log successful login
    AuditLogger.log_login(
        db, user, request.client.host, 
        request.headers.get("user-agent", ""), True
    )
    
    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds()),
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[role.name for role in user.roles if role.is_active],
            domain_access=PermissionManager.get_user_domains(user),
            last_login=user.last_login,
            created_at=user.created_at
        )
    )

@app.post("/auth/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_data: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token"""
    
    # Verify refresh token
    payload = AuthUtils.verify_token(refresh_data.refresh_token, "refresh")
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Get user and session
    user = db.query(User).filter(User.id == user_id).first()
    session = db.query(UserSession).filter(
        UserSession.user_id == user_id,
        UserSession.refresh_token == refresh_data.refresh_token,
        UserSession.is_active == True
    ).first()
    
    if not user or not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive"
        )
    
    # Create new access token
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = AuthUtils.create_access_token(
        data={"sub": str(user.id)}, 
        expires_delta=access_token_expires
    )
    
    # Update session
    session.session_token = AuthUtils.generate_session_token()  # Use unique session token
    session.expires_at = datetime.utcnow() + access_token_expires
    session.last_accessed = datetime.utcnow()
    
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=int(access_token_expires.total_seconds())
    )

@app.post("/auth/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """User logout"""
    
    # Deactivate all user sessions (simple approach)
    db.query(UserSession).filter(
        UserSession.user_id == current_user.id,
        UserSession.is_active == True
    ).update({"is_active": False})
    
    db.commit()

    # Log logout
    AuditLogger.log_logout(
        db, current_user, 
        request.client.host, 
        request.headers.get("user-agent", "")
    )
    
    return {"message": "Successfully logged out"}

# User management endpoints
@app.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create new user (admin only)"""
    
    # Validate password strength
    is_valid, errors = AuthUtils.validate_password_strength(user_data.password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"message": "Password validation failed", "errors": errors}
        )
    
    try:
        # Create user
        user = User(
            email=user_data.email,
            username=user_data.username,
            full_name=user_data.full_name,
            hashed_password=AuthUtils.get_password_hash(user_data.password),
            is_active=True,
            is_verified=True
        )
        
        # Add roles
        for role_name in user_data.roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role:
                user.roles.append(role)
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log user creation
        AuditLogger.log_event(
            db, str(current_user.id), "user_created", 
            f"Created user: {user.email}", "user", "create"
        )
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[role.name for role in user.roles],
            domain_access=PermissionManager.get_user_domains(user),
            last_login=user.last_login,
            created_at=user.created_at
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this email or username already exists"
        )

@app.get("/users/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        username=current_user.username,
        full_name=current_user.full_name,
        is_active=current_user.is_active,
        is_verified=current_user.is_verified,
        roles=[role.name for role in current_user.roles if role.is_active],
        domain_access=PermissionManager.get_user_domains(current_user),
        last_login=current_user.last_login,
        created_at=current_user.created_at
    )

@app.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List all users (admin only)"""
    
    users = db.query(User).offset(skip).limit(limit).all()
    
    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[role.name for role in user.roles if role.is_active],
            domain_access=PermissionManager.get_user_domains(user),
            last_login=user.last_login,
            created_at=user.created_at
        )
        for user in users
    ]

@app.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get user by ID (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        is_active=user.is_active,
        is_verified=user.is_verified,
        roles=[role.name for role in user.roles if role.is_active],
        domain_access=PermissionManager.get_user_domains(user),
        last_login=user.last_login,
        created_at=user.created_at
    )

@app.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update user (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Update user fields
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.username is not None:
        user.username = user_data.username
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    
    # Update roles
    if user_data.roles is not None:
        user.roles.clear()
        for role_name in user_data.roles:
            role = db.query(Role).filter(Role.name == role_name).first()
            if role:
                user.roles.append(role)
    
    try:
        db.commit()
        db.refresh(user)
        
        # Log user update
        AuditLogger.log_event(
            db, str(current_user.id), "user_updated",
            f"Updated user: {user.email}", "user", "update"
        )
        
        return UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[role.name for role in user.roles if role.is_active],
            domain_access=PermissionManager.get_user_domains(user),
            last_login=user.last_login,
            created_at=user.created_at
        )
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email or username already exists"
        )

@app.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Delete user (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent deleting yourself
    if str(user.id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own account"
        )
    
    # Soft delete - just deactivate the user
    user.is_active = False
    db.commit()
    
    # Log user deletion
    AuditLogger.log_event(
        db, str(current_user.id), "user_deleted",
        f"Deleted user: {user.email}", "user", "delete"
    )
    
    return {"message": "User successfully deleted"}

# ==== NEW RBAC ENDPOINTS ====

# Role management endpoints
@app.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Create new role (admin only)"""
    
    # Check if role already exists
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role with this name already exists"
        )
    
    try:
        role = Role(
            name=role_data.name,
            description=role_data.description,
            permissions=role_data.permissions,
            domain_access=role_data.domain_access,
            is_active=True
        )
        
        db.add(role)
        db.commit()
        db.refresh(role)
        
        # Log role creation
        AuditLogger.log_event(
            db, str(current_user.id), "role_created",
            f"Created role: {role.name}", "role", "create"
        )
        
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            domain_access=role.domain_access,
            is_active=role.is_active,
            user_count=len(role.users),
            created_at=role.created_at
        )
        
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role creation failed"
        )

@app.get("/roles", response_model=List[RoleResponse])
async def list_roles(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """List all roles (admin only)"""
    
    roles = db.query(Role).offset(skip).limit(limit).all()
    
    return [
        RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            domain_access=role.domain_access,
            is_active=role.is_active,
            user_count=len([user for user in role.users if user.is_active]),
            created_at=role.created_at
        )
        for role in roles
    ]

@app.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get role by ID (admin only)"""
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return RoleResponse(
        id=str(role.id),
        name=role.name,
        description=role.description,
        permissions=role.permissions,
        domain_access=role.domain_access,
        is_active=role.is_active,
        user_count=len([user for user in role.users if user.is_active]),
        created_at=role.created_at
    )

@app.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Update role (admin only)"""
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Update role fields
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permissions is not None:
        role.permissions = role_data.permissions
    if role_data.domain_access is not None:
        role.domain_access = role_data.domain_access
    if role_data.is_active is not None:
        role.is_active = role_data.is_active
    
    role.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(role)
        
        # Log role update
        AuditLogger.log_event(
            db, str(current_user.id), "role_updated",
            f"Updated role: {role.name}", "role", "update"
        )
        
        return RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            domain_access=role.domain_access,
            is_active=role.is_active,
            user_count=len([user for user in role.users if user.is_active]),
            created_at=role.created_at
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role update failed"
        )

@app.delete("/roles/{role_id}")
async def delete_role(
    role_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Delete role (admin only)"""
    
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Prevent deleting admin role
    if role.name == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin role"
        )
    
    # Check if role has users
    active_users = [user for user in role.users if user.is_active]
    if active_users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role with {len(active_users)} active users"
        )
    
    # Soft delete - just deactivate the role
    role.is_active = False
    db.commit()
    
    # Log role deletion
    AuditLogger.log_event(
        db, str(current_user.id), "role_deleted",
        f"Deleted role: {role.name}", "role", "delete"
    )
    
    return {"message": "Role successfully deleted"}

# User-Role assignment endpoints
@app.post("/users/{user_id}/roles/{role_name}")
async def assign_role_to_user(
    user_id: str,
    role_name: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Assign role to user (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if user already has the role
    if role in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already has this role"
        )
    
    user.roles.append(role)
    db.commit()
    
    # Log role assignment
    AuditLogger.log_event(
        db, str(current_user.id), "role_assigned",
        f"Assigned role {role_name} to user {user.email}", "user", "update"
    )
    
    return {"message": f"Role {role_name} assigned to user {user.email}"}

@app.delete("/users/{user_id}/roles/{role_name}")
async def remove_role_from_user(
    user_id: str,
    role_name: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Remove role from user (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    # Check if user has the role
    if role not in user.roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have this role"
        )
    
    # Prevent removing admin role from yourself
    if str(user.id) == str(current_user.id) and role_name == "admin":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove admin role from yourself"
        )
    
    user.roles.remove(role)
    db.commit()
    
    # Log role removal
    AuditLogger.log_event(
        db, str(current_user.id), "role_removed",
        f"Removed role {role_name} from user {user.email}", "user", "update"
    )
    
    return {"message": f"Role {role_name} removed from user {user.email}"}

@app.get("/users/{user_id}/roles", response_model=List[RoleResponse])
async def get_user_roles(
    user_id: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get all roles for a user (admin only)"""
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    return [
        RoleResponse(
            id=str(role.id),
            name=role.name,
            description=role.description,
            permissions=role.permissions,
            domain_access=role.domain_access,
            is_active=role.is_active,
            user_count=len([u for u in role.users if u.is_active]),
            created_at=role.created_at
        )
        for role in user.roles if role.is_active
    ]

@app.get("/roles/{role_name}/users", response_model=List[UserResponse])
async def get_role_users(
    role_name: str,
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get all users with a specific role (admin only)"""
    
    role = db.query(Role).filter(Role.name == role_name).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    
    return [
        UserResponse(
            id=str(user.id),
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            is_verified=user.is_verified,
            roles=[r.name for r in user.roles if r.is_active],
            domain_access=PermissionManager.get_user_domains(user),
            last_login=user.last_login,
            created_at=user.created_at
        )
        for user in role.users if user.is_active
    ]

# Permission checking endpoint
@app.post("/auth/check-permission", response_model=PermissionResponse)
async def check_permission(
    permission_check: PermissionCheck,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check user permissions"""
    
    # Get target user (can check own permissions or admin can check others)
    if str(current_user.id) == permission_check.user_id:
        target_user = current_user
    elif PermissionManager.has_role(current_user, "admin"):
        target_user = db.query(User).filter(User.id == permission_check.user_id).first()
        if not target_user:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Can only check own permissions"
        )
    
    # Check permission
    allowed, reason = PermissionManager.check_permission(
        target_user, permission_check.resource, 
        permission_check.action, permission_check.domain
    )
    
    return PermissionResponse(
        allowed=allowed,
        reason=reason,
        user_roles=[role.name for role in target_user.roles if role.is_active],
        required_permissions=[f"{permission_check.resource}:{permission_check.action}"]
    )

# Bulk permission check endpoint
@app.post("/auth/check-permissions")
async def check_multiple_permissions(
    permission_checks: List[PermissionCheck],
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Check multiple permissions at once"""
    
    results = []
    
    for check in permission_checks:
        # Get target user (can check own permissions or admin can check others)
        if str(current_user.id) == check.user_id:
            target_user = current_user
        elif PermissionManager.has_role(current_user, "admin"):
            target_user = db.query(User).filter(User.id == check.user_id).first()
            if not target_user:
                results.append({
                    "user_id": check.user_id,
                    "resource": check.resource,
                    "action": check.action,
                    "domain": check.domain,
                    "allowed": False,
                    "reason": "User not found"
                })
                continue
        else:
            results.append({
                "user_id": check.user_id,
                "resource": check.resource,
                "action": check.action,
                "domain": check.domain,
                "allowed": False,
                "reason": "Can only check own permissions"
            })
            continue
        
        # Check permission
        allowed, reason = PermissionManager.check_permission(
            target_user, check.resource, check.action, check.domain
        )
        
        results.append({
            "user_id": check.user_id,
            "resource": check.resource,
            "action": check.action,
            "domain": check.domain,
            "allowed": allowed,
            "reason": reason,
            "user_roles": [role.name for role in target_user.roles if role.is_active]
        })
    
    return {"results": results}

# Available permissions endpoint
@app.get("/permissions")
async def get_available_permissions(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get list of all available permissions (admin only)"""
    
    # Standard permission patterns
    permissions = {
        "chat": ["read", "write"],
        "files": ["read", "write", "delete"],
        "search": ["read"],
        "users": ["read", "write", "delete"],
        "roles": ["read", "write", "delete"],
        "admin": ["read", "write"],
        "analytics": ["read"],
        "audit": ["read"]
    }
    
    # Available domains
    domains = ["general", "support", "sales", "engineering", "product"]
    
    return {
        "permissions": permissions,
        "domains": domains,
        "wildcards": ["*:*", "*:read", "*:write", "resource:*"]
    }

# Statistics endpoint
@app.get("/users/stats", response_model=UserStats)
async def get_user_stats(
    current_user: User = Depends(get_admin_user),
    db: Session = Depends(get_db)
):
    """Get user statistics (admin only)"""
    
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    verified_users = db.query(User).filter(User.is_verified == True).count()
    
    # Users by role
    users_by_role = {}
    roles = db.query(Role).all()
    for role in roles:
        count = len([user for user in role.users if user.is_active])
        users_by_role[role.name] = count
    
    # Recent logins (last 24 hours)
    recent_logins = db.query(User).filter(
        User.last_login >= datetime.utcnow() - timedelta(days=1)
    ).count()
    
    return UserStats(
        total_users=total_users,
        active_users=active_users,
        verified_users=verified_users,
        users_by_role=users_by_role,
        recent_logins=recent_logins
    )

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL
    ) 