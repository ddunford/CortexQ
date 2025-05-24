"""
Enhanced Core API - Enterprise RAG Searcher
Integrated from all microservices into unified architecture
"""

import os
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
import redis
from sentence_transformers import SentenceTransformer
import uvicorn

# Import our enhanced modules
from auth_utils import (
    AuthUtils, PermissionManager, AuditLogger, SessionManager
)
from classifiers import classifier, ClassificationResult
from rag_processor import (
    initialize_rag_processor, rag_processor, RAGRequest, RAGResponse, RAGMode
)

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
    username: str
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
    
    print("🎉 Enhanced Core API started successfully!")
    
    yield
    
    print("🛑 Shutting down Enhanced Core API...")

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
        # Get user from database
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
        
        # Create RAG request
        rag_request = RAGRequest(
            query=request.message,
            domain=request.domain,
            mode=request.mode,
            max_results=request.max_results,
            confidence_threshold=request.confidence_threshold,
            context={"recent_messages": recent_messages},
            user_id=current_user["id"],
            session_id=session_id
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
    """Enhanced file upload with domain support and processing"""
    try:
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], domain):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied to domain: {domain}"
            )
        
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
        file_hash = str(hash(content))  # Simple hash for deduplication
        
        # Create file record
        file_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO files (
                    id, filename, original_filename, content_type, size_bytes,
                    file_hash, domain, uploaded_by, created_at
                ) VALUES (
                    :id, :filename, :original_filename, :content_type, :size_bytes,
                    :file_hash, :domain, :uploaded_by, :created_at
                )
            """),
            {
                "id": file_id,
                "filename": f"{file_id}_{file.filename}",
                "original_filename": file.filename,
                "content_type": file.content_type,
                "size_bytes": len(content),
                "file_hash": file_hash,
                "domain": domain,
                "uploaded_by": current_user["id"],
                "created_at": datetime.utcnow()
            }
        )
        
        # Create processing job
        job_id = str(uuid.uuid4())
        db.execute(
            text("""
                INSERT INTO file_processing_jobs (id, file_id, job_type, created_at)
                VALUES (:id, :file_id, :job_type, :created_at)
            """),
            {
                "id": job_id,
                "file_id": file_id,
                "job_type": "embedding_generation",
                "created_at": datetime.utcnow()
            }
        )
        
        db.commit()
        
        # Log file upload
        AuditLogger.log_event(
            db, "file_upload", current_user["id"], "files", "create",
            f"Uploaded file {file.filename}",
            {
                "file_id": file_id,
                "filename": file.filename,
                "size_bytes": len(content),
                "domain": domain
            }
        )
        
        # TODO: Trigger async processing
        # For now, mark as pending
        
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
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")

@app.get("/files")
async def list_files(
    domain: Optional[str] = None,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """List uploaded files"""
    # Build query based on domain access
    accessible_domains = current_user["domains"]
    
    if domain and domain not in accessible_domains:
        raise HTTPException(status_code=403, detail=f"Access denied to domain: {domain}")
    
    where_conditions = []
    params = {}
    
    if domain:
        where_conditions.append("domain = :domain")
        params["domain"] = domain
    else:
        # Filter by accessible domains
        domain_placeholders = ",".join([f":domain_{i}" for i in range(len(accessible_domains))])
        where_conditions.append(f"domain IN ({domain_placeholders})")
        for i, d in enumerate(accessible_domains):
            params[f"domain_{i}"] = d
    
    where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
    
    result = db.execute(
        text(f"""
            SELECT id, filename, original_filename, content_type, size_bytes,
                   domain, processed, processing_status, created_at
            FROM files 
            WHERE {where_clause}
            ORDER BY created_at DESC
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
            "created_at": row.created_at.isoformat()
        }
        for row in result.fetchall()
    ]

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
    """Get intent classification analytics"""
    return await classifier.get_classification_analytics(db, domain, days)

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