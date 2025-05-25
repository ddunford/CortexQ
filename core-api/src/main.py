"""
Enhanced Core API - Enterprise RAG Searcher
Integrated from all microservices into unified architecture
"""

import os
import uuid
import json
import hashlib
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
import redis
from sentence_transformers import SentenceTransformer
import uvicorn
import asyncio
import logging
from pathlib import Path
import aiofiles

# Import our enhanced modules
from auth_utils import (
    AuthUtils, PermissionManager, AuditLogger, SessionManager
)
from classifiers import classifier, ClassificationResult
from rag_processor import (
    initialize_rag_processor, rag_processor, RAGRequest, RAGResponse, RAGMode
)
# Import crawler directly to avoid dependency issues
try:
    from ingestion.crawler import WebCrawler, CrawlScheduler
    CRAWLER_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Web crawler not available: {e}")
    CRAWLER_AVAILABLE = False
    WebCrawler = None
    CrawlScheduler = None

# ============================================================================
# CONFIGURATION
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379")
JWT_SECRET = os.getenv("JWT_SECRET", "your-super-secret-jwt-key-change-in-production")
DEBUG = os.getenv("DEBUG", "true").lower() == "true"

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Redis setup
try:
    redis_client = redis.from_url(REDIS_URL)
    redis_client.ping()
except Exception:
    redis_client = None
    print("Redis not available, continuing without caching")

# Security
security = HTTPBearer()

# Global instances
embeddings_model = None
session_manager = SessionManager(redis_client)

# ============================================================================
# MODELS
# ============================================================================

class LoginRequest(BaseModel):
    username: Optional[str] = None
    email: Optional[str] = None
    password: str

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: Dict[str, Any]

class UserCreate(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    password: str
    roles: Optional[List[str]] = []

class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    full_name: Optional[str]
    is_active: bool
    roles: List[str]
    permissions: List[str]
    domains: List[str]

class ChatRequest(BaseModel):
    message: str
    domain: str = "general"
    mode: RAGMode = RAGMode.SIMPLE
    max_results: int = 5
    confidence_threshold: float = 0.3
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    intent: str
    confidence: float
    sources: List[Dict]
    session_id: str
    processing_time_ms: int
    mode_used: RAGMode
    response_type: str
    source_count: int
    suggested_actions: List[str]
    related_queries: List[str]
    agent_workflow_triggered: bool = False
    agent_workflow_id: Optional[str] = None
    execution_id: str

class FileUploadResponse(BaseModel):
    id: str
    filename: str
    status: str
    domain: str
    processing_status: str

class RoleCreate(BaseModel):
    name: str
    description: Optional[str]
    permissions: List[str]
    domain_access: List[str]

class PermissionCheck(BaseModel):
    permission: str
    resource: Optional[str] = None

class WebScrapingRequest(BaseModel):
    urls: List[str]
    domain: str = "general"
    max_depth: int = 2
    max_pages: int = 100
    delay: float = 1.0
    allowed_domains: Optional[List[str]] = None
    exclude_patterns: Optional[List[str]] = None

class WebScrapingResponse(BaseModel):
    crawl_id: str
    status: str
    urls_queued: int
    estimated_completion: str

# ============================================================================
# ORGANIZATION MODELS
# ============================================================================

class OrganizationCreate(BaseModel):
    name: str
    slug: str
    description: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size_category: str = "small"  # startup, small, medium, large, enterprise
    subscription_tier: str = "basic"  # basic, professional, enterprise

class OrganizationResponse(BaseModel):
    id: str
    name: str
    slug: str
    description: Optional[str]
    logo_url: Optional[str]
    website: Optional[str]
    industry: Optional[str]
    size_category: str
    subscription_tier: str
    max_users: int
    max_storage_gb: int
    max_domains: int
    is_active: bool
    created_at: str
    member_count: int
    domain_count: int

class OrganizationMemberResponse(BaseModel):
    id: str
    user_id: str
    username: str
    email: str
    full_name: Optional[str]
    role: str
    permissions: List[str]
    joined_at: str
    last_active: Optional[str]
    is_active: bool

class DomainTemplateResponse(BaseModel):
    id: str
    name: str
    display_name: str
    description: Optional[str]
    icon: Optional[str]
    color: Optional[str]
    category: str
    suggested_settings: Dict

class OrganizationDomainCreate(BaseModel):
    domain_name: str
    display_name: str
    description: Optional[str] = None
    icon: str = "globe"
    color: str = "blue"
    settings: Dict = {}
    template_id: Optional[str] = None

class OrganizationDomainResponse(BaseModel):
    id: str
    organization_id: str
    domain_name: str
    display_name: str
    description: Optional[str]
    icon: str
    color: str
    settings: Dict
    created_by: Optional[str]
    is_active: bool
    created_at: str

class InvitationCreate(BaseModel):
    email: str
    role: str = "user"

class InvitationResponse(BaseModel):
    id: str
    organization_id: str
    email: str
    role: str
    invited_by: str
    invitation_token: str
    expires_at: str
    created_at: str

# ============================================================================
# DEPENDENCY INJECTION
# ============================================================================

def get_db():
    """Database dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current authenticated user"""
    try:
        # Extract token
        token = credentials.credentials
        
        # Verify token
        payload = AuthUtils.verify_token(token, "access")
        if not payload:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        
        # Get user from database
        result = db.execute(
            text("SELECT id, username, email, full_name, is_active, is_superuser FROM users WHERE id = :user_id"),
            {"user_id": user_id}
        )
        user = result.fetchone()
        
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found or inactive")
        
        # Get user roles and permissions
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
        return {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "is_active": user.is_active,
            "is_superuser": user.is_superuser,
            "roles": roles,
            "permissions": permissions,
            "domains": domains
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")

def require_permission(permission: str):
    """Decorator to require specific permission"""
    def permission_dependency(
        current_user: dict = Depends(get_current_user),
        db: Session = Depends(get_db)
    ):
        if not PermissionManager.has_permission(db, current_user["id"], permission):
            raise HTTPException(
                status_code=403,
                detail=f"Permission denied: {permission} required"
            )
        return current_user
    return permission_dependency

def require_admin():
    """Require admin role"""
    def admin_dependency(current_user: dict = Depends(get_current_user)):
        if not PermissionManager.is_admin(current_user["roles"]):
            raise HTTPException(status_code=403, detail="Admin access required")
        return current_user
    return admin_dependency

# ============================================================================
# APPLICATION LIFECYCLE
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    global embeddings_model, rag_processor
    
    print("🚀 Starting Enhanced Core API...")
    
    # Initialize embeddings model
    try:
        print("Loading embeddings model...")
        embeddings_model = SentenceTransformer('all-MiniLM-L6-v2')
        print("✅ Embeddings model loaded")
    except Exception as e:
        print(f"❌ Failed to load embeddings model: {e}")
        embeddings_model = None
    
    # Initialize RAG processor
    if embeddings_model:
        try:
            print("Initializing RAG processor...")
            initialize_rag_processor(embeddings_model)
            print("✅ RAG processor initialized")
        except Exception as e:
            print(f"❌ Failed to initialize RAG processor: {e}")
    
    # Start background processor
    try:
        from background_processor import start_background_processor
        asyncio.create_task(start_background_processor())
        print("✅ Background processor started")
    except ImportError:
        print("⚠️ Background processor not available")
    
    print("🎉 Enhanced Core API started successfully!")
    
    yield
    
    print("🛑 Shutting down Enhanced Core API...")
    
    # Stop background processor
    try:
        from background_processor import stop_background_processor
        stop_background_processor()
        print("✅ Background processor stopped")
    except ImportError:
        pass

# ============================================================================
# APPLICATION SETUP
# ============================================================================

app = FastAPI(
    title="Enhanced Core API - Enterprise RAG Searcher",
    description="Unified API with RBAC, multi-domain RAG, intent classification, and enterprise features",
    version="2.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# HEALTH & STATUS ENDPOINTS
# ============================================================================

@app.get("/health")
async def health_check():
    """Enhanced health check with service status"""
    return {
        "status": "healthy",
        "service": "enhanced-core-api",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": "connected",
            "redis": "connected" if redis_client else "unavailable",
            "embeddings": "loaded" if embeddings_model else "unavailable",
            "rag_processor": "initialized" if rag_processor else "unavailable"
        }
    }

@app.get("/status")
async def status_check(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Detailed status for authenticated users"""
    # Get system statistics
    stats = db.execute(text("""
        SELECT 
            (SELECT COUNT(*) FROM users) as total_users,
            (SELECT COUNT(*) FROM files) as total_files,
            (SELECT COUNT(*) FROM embeddings) as total_embeddings,
            (SELECT COUNT(*) FROM chat_sessions WHERE created_at > NOW() - INTERVAL '24 hours') as active_sessions
    """)).fetchone()
    
    return {
        "system": {
            "status": "operational",
            "uptime": "running",
            "version": "2.0.0"
        },
        "statistics": {
            "total_users": stats.total_users,
            "total_files": stats.total_files,
            "total_embeddings": stats.total_embeddings,
            "active_sessions_24h": stats.active_sessions
        },
        "user": {
            "id": current_user["id"],
            "username": current_user["username"],
            "roles": current_user["roles"],
            "accessible_domains": current_user["domains"]
        }
    }

# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/auth/login", response_model=LoginResponse)
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
        
        # Get user roles, permissions, and domains
        user_id = str(user.id)
        roles = PermissionManager.get_user_roles(db, user_id)
        permissions = PermissionManager.get_user_permissions(db, user_id)
        domains = PermissionManager.get_user_domains(db, user_id)
        
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

@app.post("/auth/logout")
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

@app.post("/auth/register", response_model=UserResponse)
async def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """Register a new user (public endpoint)"""
    try:
        # Check if user already exists
        existing_user = db.execute(
            text("SELECT id FROM users WHERE username = :username OR email = :email"),
            {"username": user_data.username, "email": user_data.email}
        ).fetchone()
        
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
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
                "username": user_data.username,
                "email": user_data.email,
                "full_name": user_data.full_name,
                "password_hash": password_hash,
                "created_at": datetime.utcnow()
            }
        )
        
        # Assign default user role
        default_roles = user_data.roles if user_data.roles else ["user"]
        for role_name in default_roles:
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
        
        # Log user registration
        AuditLogger.log_event(
            db, "user_registration", user_id, "users", "create",
            f"User {user_data.username} registered",
            {"roles": roles}
        )
        
        return UserResponse(
            id=user_id,
            username=user_data.username,
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

# ============================================================================
# USER MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/users", response_model=UserResponse)
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
                "username": user_data.username,
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
            f"Created user {user_data.username}",
            {"new_user_id": user_id, "roles": roles}
        )
        
        return UserResponse(
            id=user_id,
            username=user_data.username,
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

@app.get("/users/me", response_model=UserResponse)
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

# ============================================================================
# ROLE & PERMISSION MANAGEMENT
# ============================================================================

@app.get("/roles")
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

@app.post("/roles")
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

@app.post("/auth/check-permission")
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

# ============================================================================
# CHAT & RAG ENDPOINTS
# ============================================================================

@app.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(require_permission("chat:write")),
    db: Session = Depends(get_db)
):
    """Enhanced chat with intent classification and RAG"""
    try:
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], request.domain):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to domain: {request.domain}"
            )
        
        # Create session if not provided
        session_id = request.session_id or str(uuid.uuid4())
        
        # Ensure chat session exists
        db.execute(
            text("""
                INSERT INTO chat_sessions (id, session_id, user_id, domain, created_at)
                VALUES (:id, :session_id, :user_id, :domain, :created_at)
                ON CONFLICT (session_id) DO NOTHING
            """),
            {
                "id": str(uuid.uuid4()),
                "session_id": session_id,
                "user_id": current_user["id"],
                "domain": request.domain,
                "created_at": datetime.utcnow()
            }
        )
        
        # Get conversation context
        context_result = db.execute(
            text("""
                SELECT cm.content, cm.message_type, cm.created_at
                FROM chat_messages cm
                JOIN chat_sessions cs ON cm.session_id = cs.id
                WHERE cs.session_id = :session_id
                ORDER BY cm.created_at DESC
                LIMIT 5
            """),
            {"session_id": session_id}
        )
        
        recent_messages = [
            {
                "content": row.content,
                "type": row.message_type,
                "timestamp": row.created_at.isoformat()
            }
            for row in context_result.fetchall()
        ]
        
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)

        # Create RAG request with organization context
        rag_request = RAGRequest(
            query=request.message,
            domain=request.domain,
            mode=request.mode,
            max_results=request.max_results,
            confidence_threshold=request.confidence_threshold,
            context={"recent_messages": recent_messages},
            user_id=current_user["id"],
            session_id=session_id,
            organization_id=organization_id
        )
        
        # Process with RAG
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        rag_response = await rag_processor.process_query(rag_request, db)
        
        # Get session record
        session_result = db.execute(
            text("SELECT id FROM chat_sessions WHERE session_id = :session_id"),
            {"session_id": session_id}
        )
        session_record = session_result.fetchone()
        
        if session_record:
            # Store user message
            db.execute(
                text("""
                    INSERT INTO chat_messages (id, session_id, message_type, content, created_at)
                    VALUES (:id, :session_id, :message_type, :content, :created_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_record.id,
                    "message_type": "user",
                    "content": request.message,
                    "created_at": datetime.utcnow()
                }
            )
            
            # Store assistant response
            db.execute(
                text("""
                    INSERT INTO chat_messages (id, session_id, message_type, content, intent, confidence, sources, created_at)
                    VALUES (:id, :session_id, :message_type, :content, :intent, :confidence, :sources, :created_at)
                """),
                {
                    "id": str(uuid.uuid4()),
                    "session_id": session_record.id,
                    "message_type": "assistant",
                    "content": rag_response.response,
                    "intent": rag_response.intent,
                    "confidence": rag_response.confidence,
                    "sources": json.dumps(rag_response.sources),
                    "created_at": datetime.utcnow()
                }
            )
        
        db.commit()
        
        # Log chat interaction
        AuditLogger.log_event(
            db, "chat_interaction", current_user["id"], "chat", "query",
            f"Chat query in domain {request.domain}",
            {
                "query_length": len(request.message),
                "intent": rag_response.intent,
                "confidence": rag_response.confidence,
                "domain": request.domain
            }
        )
        
        return ChatResponse(
            response=rag_response.response,
            intent=rag_response.intent,
            confidence=rag_response.confidence,
            sources=rag_response.sources,
            session_id=session_id,
            processing_time_ms=rag_response.processing_time_ms,
            mode_used=rag_response.mode_used,
            response_type=rag_response.response_type,
            source_count=len(rag_response.sources),
            suggested_actions=rag_response.suggested_actions,
            related_queries=rag_response.related_queries,
            agent_workflow_triggered=rag_response.agent_workflow_triggered,
            agent_workflow_id=rag_response.agent_workflow_id,
            execution_id=rag_response.execution_id
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

# ============================================================================
# FILE MANAGEMENT ENDPOINTS
# ============================================================================

@app.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    domain: str = Form("general"),
    current_user: dict = Depends(require_permission("files:write")),
    db: Session = Depends(get_db)
):
    """Enhanced file upload with domain support, multi-tenant isolation, and processing"""
    try:
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], domain):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to domain: {domain}"
            )
        
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id, o.slug
                FROM organization_members om
                JOIN organizations o ON om.organization_id = o.id
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        org_slug = org_result.slug
        
        # Validate file type
        allowed_types = {
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "text/plain",
            "text/markdown",
            "application/json",
            "text/csv"
        }
        
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {file.content_type}"
            )
        
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: 50MB"
            )
        
        # Generate secure file hash for deduplication
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicate files within the organization
        existing_file = db.execute(
            text("""
                SELECT id, original_filename FROM files 
                WHERE file_hash = :file_hash AND organization_id = :org_id
            """),
            {"file_hash": file_hash, "org_id": organization_id}
        ).fetchone()
        
        if existing_file:
            return FileUploadResponse(
                id=str(existing_file.id),
                filename=existing_file.original_filename,
                status="duplicate",
                domain=domain,
                processing_status="completed"
            )
        
        # Create multi-tenant file storage structure
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix.lower()
        safe_filename = f"{file_id}{file_extension}"
        
        # Multi-tenant storage path: /uploads/{org_slug}/{domain}/{file_id}.ext
        storage_base = Path(os.getenv("FILE_STORAGE_PATH", "./uploads"))
        org_storage_path = storage_base / org_slug / domain
        org_storage_path.mkdir(parents=True, exist_ok=True)
        
        file_path = org_storage_path / safe_filename
        
        # Save file to disk with proper isolation
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Create file record with organization and file path
        db.execute(
            text("""
                INSERT INTO files (
                    id, filename, original_filename, content_type, size_bytes,
                    file_hash, file_path, domain, organization_id, uploaded_by, created_at
                ) VALUES (
                    :id, :filename, :original_filename, :content_type, :size_bytes,
                    :file_hash, :file_path, :domain, :organization_id, :uploaded_by, :created_at
                )
            """),
            {
                "id": file_id,
                "filename": safe_filename,
                "original_filename": file.filename,
                "content_type": file.content_type,
                "size_bytes": file_size,
                "file_hash": file_hash,
                "file_path": str(file_path),
                "domain": domain,
                "organization_id": organization_id,
                "uploaded_by": current_user["id"],
                "created_at": datetime.utcnow()
            }
        )
        
        # Create processing job with organization context
        job_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO file_processing_jobs (
                    id, file_id, job_type, organization_id, domain, created_at
                ) VALUES (
                    :id, :file_id, :job_type, :organization_id, :domain, :created_at
                )
            """),
            {
                "id": job_id,
                "file_id": file_id,
                "job_type": "embedding_generation",
                "organization_id": organization_id,
                "domain": domain,
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log file upload with organization context
        AuditLogger.log_event(
            db, "file_upload", current_user["id"], "files", "create",
            f"Uploaded file {file.filename} to domain {domain}",
            {
                "file_id": file_id,
                "filename": file.filename,
                "size_bytes": file_size,
                "domain": domain,
                "organization_id": organization_id,
                "file_path": str(file_path)
            }
        )
        
        # Trigger async processing
        try:
            from background_processor import background_processor
            if background_processor:
                logger.info(f"File {file_id} queued for processing in org {org_slug}")
        except ImportError:
            logger.warning("Background processor not available")
        
        return FileUploadResponse(
            id=file_id,
            filename=file.filename,
            status="uploaded",
            domain=domain,
            processing_status="pending"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Clean up file if it was created
        try:
            if 'file_path' in locals() and Path(file_path).exists():
                Path(file_path).unlink()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.get("/files")
async def list_files(
    domain: Optional[str] = None,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """List uploaded files with multi-tenant isolation"""
    try:
        # Get user's organization
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        # Build query based on domain access within organization
        accessible_domains = current_user["domains"]
        
        if domain and domain not in accessible_domains:
            raise HTTPException(status_code=403, detail=f"Access denied to domain: {domain}")
        
        where_conditions = ["f.organization_id = :organization_id"]
        params = {"organization_id": organization_id}
        
        if domain:
            where_conditions.append("f.domain = :domain")
            params["domain"] = domain
        else:
            # Filter by accessible domains within the organization
            if accessible_domains:
                domain_placeholders = ",".join([f":domain_{i}" for i in range(len(accessible_domains))])
                where_conditions.append(f"f.domain IN ({domain_placeholders})")
                for i, d in enumerate(accessible_domains):
                    params[f"domain_{i}"] = d
        
        where_clause = " AND ".join(where_conditions)
        
        result = db.execute(
            text(f"""
                SELECT f.id, f.filename, f.original_filename, f.content_type, f.size_bytes,
                       f.domain, f.processed, f.processing_status, f.processing_error, f.created_at,
                       u.username as uploaded_by_username
                FROM files f
                LEFT JOIN users u ON f.uploaded_by = u.id
                WHERE {where_clause}
                ORDER BY f.created_at DESC
                LIMIT 100
            """),
            params
        )
        
        return [
            {
                "id": str(row.id),
                "filename": row.filename,
                "original_filename": row.original_filename,
                "content_type": row.content_type,
                "size_bytes": row.size_bytes,
                "domain": row.domain,
                "processed": row.processed,
                "processing_status": row.processing_status,
                "processing_error": row.processing_error,
                "uploaded_by": row.uploaded_by_username,
                "created_at": row.created_at.isoformat()
            }
            for row in result.fetchall()
        ]
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")

# ============================================================================
# WEB SCRAPING ENDPOINTS
# ============================================================================

@app.post("/web-scraping/start", response_model=WebScrapingResponse)
async def start_web_scraping(
    request: WebScrapingRequest,
    current_user: dict = Depends(require_permission("files:write")),
    db: Session = Depends(get_db)
):
    """Start web scraping for specified URLs with multi-tenant isolation"""
    if not CRAWLER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Web crawler service not available")
    
    try:
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id, o.slug
                FROM organization_members om
                JOIN organizations o ON om.organization_id = o.id
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        org_slug = org_result.slug
        
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], request.domain):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to domain: {request.domain}"
            )
        
        # Generate crawl ID
        crawl_id = str(uuid.uuid4())
        
        # Set up allowed domains if not provided
        if not request.allowed_domains:
            request.allowed_domains = []
            for url in request.urls:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc not in request.allowed_domains:
                    request.allowed_domains.append(parsed.netloc)
        
        # Initialize crawler scheduler
        scheduler = CrawlScheduler()
        
        # Create crawl configuration with organization context
        crawl_config = {
            "crawl_id": crawl_id,
            "urls": request.urls,
            "domain": request.domain,
            "organization_id": organization_id,
            "org_slug": org_slug,
            "max_depth": request.max_depth,
            "max_pages": request.max_pages,
            "delay": request.delay,
            "allowed_domains": request.allowed_domains,
            "exclude_patterns": request.exclude_patterns or [],
            "user_id": current_user["id"],
            "created_at": datetime.utcnow().isoformat()
        }
        
        # Schedule the crawl
        await scheduler.schedule_crawl(crawl_config, db)
        
        # Estimate completion time (rough calculation)
        estimated_pages = min(request.max_pages, len(request.urls) * (request.max_depth ** 2))
        estimated_seconds = estimated_pages * request.delay
        estimated_completion = (datetime.utcnow() + timedelta(seconds=estimated_seconds)).isoformat()
        
        # Log the action with organization context
        AuditLogger.log_event(
            db, "web_scraping_started", current_user["id"], "crawl", "create",
            f"Started web scraping for {len(request.urls)} URLs in domain {request.domain}",
            {
                "crawl_id": crawl_id,
                "urls": request.urls,
                "domain": request.domain,
                "organization_id": organization_id,
                "max_pages": request.max_pages,
                "max_depth": request.max_depth
            }
        )
        
        return WebScrapingResponse(
            crawl_id=crawl_id,
            status="scheduled",
            urls_queued=len(request.urls),
            estimated_completion=estimated_completion
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start web scraping: {str(e)}")

@app.get("/web-scraping/{crawl_id}/status")
async def get_crawl_status(
    crawl_id: str,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Get status of a web crawling job with multi-tenant isolation"""
    try:
        # Get user's organization
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        # Query crawl job with organization isolation
        result = db.execute(
            text("""
                SELECT crawl_id, status, pages_crawled, total_pages, started_at, completed_at, error_message
                FROM crawl_jobs
                WHERE crawl_id = :crawl_id AND user_id = :user_id AND organization_id = :organization_id
            """),
            {
                "crawl_id": crawl_id, 
                "user_id": current_user["id"],
                "organization_id": organization_id
            }
        ).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Crawl job not found")
        
        return {
            "crawl_id": result.crawl_id,
            "status": result.status,
            "pages_crawled": result.pages_crawled or 0,
            "total_pages": result.total_pages or 0,
            "progress_percentage": (result.pages_crawled / max(result.total_pages, 1)) * 100 if result.total_pages else 0,
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_message": result.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawl status: {str(e)}")

# ============================================================================
# ANALYTICS & REPORTING ENDPOINTS
# ============================================================================

@app.get("/analytics/classification")
async def get_classification_analytics(
    domain: Optional[str] = None,
    days: int = 7,
    current_user: dict = Depends(require_permission("analytics:read")),
    db: Session = Depends(get_db)
):
    """Get intent classification analytics with organization isolation"""
    try:
        # Get user's organization for multi-tenant isolation
        org_result = db.execute(
            text("""
                SELECT om.organization_id
                FROM organization_members om
                WHERE om.user_id = :user_id AND om.is_active = true
                LIMIT 1
            """),
            {"user_id": current_user["id"]}
        ).fetchone()
        
        if not org_result:
            raise HTTPException(status_code=403, detail="User not associated with any organization")
        
        organization_id = str(org_result.organization_id)
        
        return await classifier.get_classification_analytics(db, organization_id, domain, days)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get classification analytics: {str(e)}")

@app.get("/analytics/rag")
async def get_rag_analytics(
    domain: Optional[str] = None,
    days: int = 7,
    current_user: dict = Depends(require_permission("analytics:read")),
    db: Session = Depends(get_db)
):
    """Get enhanced RAG analytics with mode distribution and performance metrics"""
    try:
        if not rag_processor:
            raise HTTPException(status_code=503, detail="RAG processor not available")
        
        analytics = await rag_processor.get_analytics(db, domain, days)
        return analytics
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get RAG analytics: {str(e)}")

@app.get("/analytics/audit")
async def get_audit_analytics(
    days: int = 7,
    current_user: dict = Depends(require_admin()),
    db: Session = Depends(get_db)
):
    """Get audit event analytics"""
    result = db.execute(
        text("""
            SELECT 
                event_type,
                COUNT(*) as count,
                COUNT(DISTINCT user_id) as unique_users
            FROM audit_events
            WHERE created_at >= NOW() - INTERVAL '%s days'
            GROUP BY event_type
            ORDER BY count DESC
        """ % days)
    )
    
    return [
        {
            "event_type": row.event_type,
            "count": row.count,
            "unique_users": row.unique_users
        }
        for row in result.fetchall()
    ]

# ============================================================================
# ORGANIZATION MANAGEMENT ENDPOINTS
# ============================================================================

@app.get("/organizations", response_model=List[OrganizationResponse])
async def list_organizations(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List organizations the user has access to"""
    result = db.execute(
        text("""
            SELECT DISTINCT o.id, o.name, o.slug, o.description, o.logo_url, o.website,
                   o.industry, o.size_category, o.subscription_tier, o.max_users,
                   o.max_storage_gb, o.max_domains, o.is_active, o.created_at,
                   (SELECT COUNT(*) FROM organization_members om WHERE om.organization_id = o.id AND om.is_active = true) as member_count,
                   (SELECT COUNT(*) FROM organization_domains od WHERE od.organization_id = o.id AND od.is_active = true) as domain_count
            FROM organizations o
            JOIN organization_members om ON o.id = om.organization_id
            WHERE om.user_id = :user_id AND om.is_active = true AND o.is_active = true
            ORDER BY o.name
        """),
        {"user_id": current_user["id"]}
    )
    
    return [
        OrganizationResponse(
            id=str(row.id),
            name=row.name,
            slug=row.slug,
            description=row.description,
            logo_url=row.logo_url,
            website=row.website,
            industry=row.industry,
            size_category=row.size_category,
            subscription_tier=row.subscription_tier,
            max_users=row.max_users,
            max_storage_gb=row.max_storage_gb,
            max_domains=row.max_domains,
            is_active=row.is_active,
            created_at=row.created_at.isoformat(),
            member_count=row.member_count,
            domain_count=row.domain_count
        )
        for row in result.fetchall()
    ]

@app.post("/organizations", response_model=OrganizationResponse)
async def create_organization(
    org_data: OrganizationCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new organization"""
    try:
        # Check if slug is available
        existing = db.execute(
            text("SELECT id FROM organizations WHERE slug = :slug"),
            {"slug": org_data.slug}
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Organization slug already exists")
        
        # Set limits based on subscription tier
        tier_limits = {
            "basic": {"max_users": 10, "max_storage_gb": 10, "max_domains": 3},
            "professional": {"max_users": 50, "max_storage_gb": 100, "max_domains": 10},
            "enterprise": {"max_users": 1000, "max_storage_gb": 1000, "max_domains": 50}
        }
        limits = tier_limits.get(org_data.subscription_tier, tier_limits["basic"])
        
        # Create organization
        org_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organizations (
                    id, name, slug, description, logo_url, website, industry,
                    size_category, subscription_tier, max_users, max_storage_gb, max_domains,
                    created_at
                ) VALUES (
                    :id, :name, :slug, :description, :logo_url, :website, :industry,
                    :size_category, :subscription_tier, :max_users, :max_storage_gb, :max_domains,
                    :created_at
                )
            """),
            {
                "id": org_id,
                "name": org_data.name,
                "slug": org_data.slug,
                "description": org_data.description,
                "logo_url": org_data.logo_url,
                "website": org_data.website,
                "industry": org_data.industry,
                "size_category": org_data.size_category,
                "subscription_tier": org_data.subscription_tier,
                "max_users": limits["max_users"],
                "max_storage_gb": limits["max_storage_gb"],
                "max_domains": limits["max_domains"],
                "created_at": datetime.utcnow()
            }
        )
        
        # Add creator as owner
        db.execute(
            text("""
                INSERT INTO organization_members (organization_id, user_id, role, joined_at)
                VALUES (:org_id, :user_id, 'owner', :joined_at)
            """),
            {
                "org_id": org_id,
                "user_id": current_user["id"],
                "joined_at": datetime.utcnow()
            }
        )
        
        # Create default general domain
        domain_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_domains (
                    id, organization_id, domain_name, display_name, description,
                    icon, color, created_by, created_at
                ) VALUES (
                    :id, :org_id, 'general', 'General', 'General knowledge and documentation',
                    'globe', 'blue', :created_by, :created_at
                )
            """),
            {
                "id": domain_id,
                "org_id": org_id,
                "created_by": current_user["id"],
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log organization creation
        AuditLogger.log_event(
            db, "organization_creation", current_user["id"], "organizations", "create",
            f"Created organization {org_data.name}",
            {"organization_id": org_id, "slug": org_data.slug}
        )
        
        return OrganizationResponse(
            id=org_id,
            name=org_data.name,
            slug=org_data.slug,
            description=org_data.description,
            logo_url=org_data.logo_url,
            website=org_data.website,
            industry=org_data.industry,
            size_category=org_data.size_category,
            subscription_tier=org_data.subscription_tier,
            max_users=limits["max_users"],
            max_storage_gb=limits["max_storage_gb"],
            max_domains=limits["max_domains"],
            is_active=True,
            created_at=datetime.utcnow().isoformat(),
            member_count=1,
            domain_count=1
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create organization: {str(e)}")

@app.get("/organizations/{org_id}/domains", response_model=List[OrganizationDomainResponse])
async def list_organization_domains(
    org_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List domains for an organization"""
    # Check if user has access to this organization
    member = db.execute(
        text("""
            SELECT role FROM organization_members 
            WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
        """),
        {"org_id": org_id, "user_id": current_user["id"]}
    ).fetchone()
    
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to organization")
    
    result = db.execute(
        text("""
            SELECT id, organization_id, domain_name, display_name, description,
                   icon, color, settings, created_by, is_active, created_at
            FROM organization_domains
            WHERE organization_id = :org_id AND is_active = true
            ORDER BY domain_name
        """),
        {"org_id": org_id}
    )
    
    return [
        OrganizationDomainResponse(
            id=str(row.id),
            organization_id=str(row.organization_id),
            domain_name=row.domain_name,
            display_name=row.display_name,
            description=row.description,
            icon=row.icon,
            color=row.color,
            settings=row.settings or {},
            created_by=str(row.created_by) if row.created_by else None,
            is_active=row.is_active,
            created_at=row.created_at.isoformat()
        )
        for row in result.fetchall()
    ]

@app.post("/organizations/{org_id}/domains", response_model=OrganizationDomainResponse)
async def create_organization_domain(
    org_id: str,
    domain_data: OrganizationDomainCreate,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new domain for an organization"""
    try:
        # Check if user has admin access to this organization
        member = db.execute(
            text("""
                SELECT role FROM organization_members 
                WHERE organization_id = :org_id AND user_id = :user_id AND is_active = true
            """),
            {"org_id": org_id, "user_id": current_user["id"]}
        ).fetchone()
        
        if not member or member.role not in ['owner', 'admin']:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Check domain limits
        org_info = db.execute(
            text("SELECT max_domains FROM organizations WHERE id = :org_id"),
            {"org_id": org_id}
        ).fetchone()
        
        current_domains = db.execute(
            text("SELECT COUNT(*) as count FROM organization_domains WHERE organization_id = :org_id AND is_active = true"),
            {"org_id": org_id}
        ).fetchone()
        
        if current_domains.count >= org_info.max_domains:
            raise HTTPException(status_code=400, detail="Domain limit reached for this organization")
        
        # Check if domain name is unique within organization
        existing = db.execute(
            text("SELECT id FROM organization_domains WHERE organization_id = :org_id AND domain_name = :domain_name"),
            {"org_id": org_id, "domain_name": domain_data.domain_name}
        ).fetchone()
        
        if existing:
            raise HTTPException(status_code=400, detail="Domain name already exists in this organization")
        
        # Get template settings if template_id provided
        settings = domain_data.settings
        if domain_data.template_id:
            template = db.execute(
                text("SELECT suggested_settings FROM domain_templates WHERE id = :template_id"),
                {"template_id": domain_data.template_id}
            ).fetchone()
            if template:
                settings.update(template.suggested_settings or {})
        
        # Create domain
        domain_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO organization_domains (
                    id, organization_id, domain_name, display_name, description,
                    icon, color, settings, created_by, created_at
                ) VALUES (
                    :id, :org_id, :domain_name, :display_name, :description,
                    :icon, :color, :settings, :created_by, :created_at
                )
            """),
            {
                "id": domain_id,
                "org_id": org_id,
                "domain_name": domain_data.domain_name,
                "display_name": domain_data.display_name,
                "description": domain_data.description,
                "icon": domain_data.icon,
                "color": domain_data.color,
                "settings": json.dumps(settings),
                "created_by": current_user["id"],
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log domain creation
        AuditLogger.log_event(
            db, "domain_creation", current_user["id"], "organization_domains", "create",
            f"Created domain {domain_data.domain_name} in organization {org_id}",
            {"domain_id": domain_id, "domain_name": domain_data.domain_name}
        )
        
        return OrganizationDomainResponse(
            id=domain_id,
            organization_id=org_id,
            domain_name=domain_data.domain_name,
            display_name=domain_data.display_name,
            description=domain_data.description,
            icon=domain_data.icon,
            color=domain_data.color,
            settings=settings,
            created_by=current_user["id"],
            is_active=True,
            created_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create domain: {str(e)}")

@app.get("/domain-templates", response_model=List[DomainTemplateResponse])
async def list_domain_templates(
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List available domain templates"""
    where_clause = "WHERE is_active = true"
    params = {}
    
    if category:
        where_clause += " AND category = :category"
        params["category"] = category
    
    result = db.execute(
        text(f"""
            SELECT id, name, display_name, description, icon, color, category, suggested_settings
            FROM domain_templates
            {where_clause}
            ORDER BY category, display_name
        """),
        params
    )
    
    return [
        DomainTemplateResponse(
            id=str(row.id),
            name=row.name,
            display_name=row.display_name,
            description=row.description,
            icon=row.icon,
            color=row.color,
            category=row.category,
            suggested_settings=row.suggested_settings or {}
        )
        for row in result.fetchall()
    ]

# ============================================================================
# MAIN APPLICATION
# ============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=DEBUG,
        log_level="debug" if DEBUG else "info"
    ) 