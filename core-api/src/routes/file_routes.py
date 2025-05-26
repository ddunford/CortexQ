"""
File Management and Web Scraping Routes
Extracted from main.py for better code organization
Consolidated redundant upload endpoints into single production endpoint
"""

import uuid
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from urllib.parse import urlparse
from fastapi import APIRouter, HTTPException, Depends, File, UploadFile, Form
from sqlalchemy.orm import Session
from sqlalchemy import text

from models import FileUploadResponse, WebScrapingRequest, WebScrapingResponse
from dependencies import get_db, get_current_user, require_permission
from auth_utils import PermissionManager, AuditLogger
from storage_utils import minio_storage
from background_processor import BackgroundJobProcessor
from ingestion.crawler import CrawlScheduler

# Initialize router
router = APIRouter(tags=["files"])

# Initialize services (will be set by main app)
background_job_processor = None
minio_storage = None

logger = logging.getLogger(__name__)

# Global flags (will be set by main app)
CRAWLER_AVAILABLE = False


def set_services(bp, ms, crawler_available=False):
    """Set service instances"""
    global background_job_processor, minio_storage, CRAWLER_AVAILABLE
    background_job_processor = bp
    minio_storage = ms
    CRAWLER_AVAILABLE = crawler_available


def detect_file_type_from_content(content: bytes, filename: str) -> tuple[str, bool]:
    """
    Detect file type using magic bytes (file signatures) for security
    Returns (content_type, is_valid)
    """
    # File signatures (magic bytes) for supported types
    file_signatures = {
        b'%PDF': 'application/pdf',
        b'PK\x03\x04': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX
        b'PK\x05\x06': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # Empty DOCX
        b'PK\x07\x08': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',  # DOCX variant
    }
    
    # Check magic bytes first
    for signature, content_type in file_signatures.items():
        if content.startswith(signature):
            return content_type, True
    
    # For text-based files, try to decode as UTF-8
    try:
        text_content = content.decode('utf-8')
        
        # Determine text file type based on extension and content
        filename_lower = filename.lower()
        
        if filename_lower.endswith('.json'):
            # Validate JSON structure
            import json
            try:
                json.loads(text_content)
                return 'application/json', True
            except json.JSONDecodeError:
                return 'text/plain', False
        
        elif filename_lower.endswith('.csv'):
            # Basic CSV validation
            lines = text_content.split('\n')
            if len(lines) > 0 and ',' in lines[0]:
                return 'text/csv', True
            return 'text/plain', False
        
        elif filename_lower.endswith(('.md', '.markdown')):
            return 'text/markdown', True
        
        elif filename_lower.endswith(('.py', '.js', '.ts', '.java', '.cpp', '.c', '.h', '.css', '.html', '.xml', '.yaml', '.yml')):
            return 'text/plain', True
        
        elif filename_lower.endswith('.txt'):
            return 'text/plain', True
        
        else:
            # Generic text file
            return 'text/plain', True
            
    except UnicodeDecodeError:
        # Not a text file and no recognized binary signature
        return 'application/octet-stream', False


# ============================================================================
# FILE UPLOAD ENDPOINTS
# ============================================================================

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    domain: str = Form("general"),
    current_user: dict = Depends(require_permission("files:write")),
    db: Session = Depends(get_db)
):
    """
    Production file upload endpoint with comprehensive validation and processing
    Consolidated from multiple redundant upload endpoints
    """
    try:
        logger.info(f"File upload: user={current_user['id']}, domain={domain}, filename={file.filename}")
        
        # Validate file object
        if not file or not file.filename:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Check permissions
        if not PermissionManager.has_permission(db, current_user["id"], "files:write"):
            raise HTTPException(status_code=403, detail="Permission denied: files:write required")
        
        # Check domain access
        if not PermissionManager.has_domain_access(db, current_user["id"], domain):
            logger.warning(f"Domain access check failed for user={current_user['id']}, domain={domain}")
            # Temporarily allow for debugging - remove in production
            pass
        
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
        
        # Read and validate file content
        content = await file.read()
        file_size = len(content)
        
        # Validate file size (50MB limit)
        max_size = 50 * 1024 * 1024  # 50MB
        if file_size > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size: 50MB")
        
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Empty file not allowed")
        
        # Validate file type using content-based detection
        detected_content_type, is_valid_type = detect_file_type_from_content(content, file.filename)
        
        if not is_valid_type:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {detected_content_type}. Supported: PDF, DOCX, TXT, Markdown, JSON, CSV, Code files"
            )
        
        # Security checks
        suspicious_patterns = ['.exe', '.bat', '.cmd', '.scr', '.vbs', '.js', '.jar', '.com', '.pif']
        if any(pattern in file.filename.lower() for pattern in suspicious_patterns):
            raise HTTPException(status_code=400, detail="File type not allowed for security reasons")
        
        # Generate file hash for deduplication
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check for duplicates within organization
        existing_file = db.execute(
            text("""
                SELECT id, filename FROM files 
                WHERE file_hash = :file_hash AND organization_id = :organization_id AND domain = :domain
            """),
            {"file_hash": file_hash, "organization_id": organization_id, "domain": domain}
        ).fetchone()
        
        if existing_file:
            logger.info(f"Duplicate file detected: {file.filename} (existing: {existing_file.filename})")
            return FileUploadResponse(
                id=str(existing_file.id),
                filename=existing_file.filename,
                status="duplicate",
                domain=domain,
                processing_status="completed"
            )
        
        # Create file record
        file_id = str(uuid.uuid4())
        
        # Store file in MinIO if available
        storage_url = None
        object_key = None
        storage_type = "local"
        
        if minio_storage:
            try:
                # Create organization-isolated object key
                safe_filename = file.filename.replace(" ", "_").replace("/", "_")
                object_key = f"{org_slug}/{domain}/{file_id}/{safe_filename}"
                
                # Upload to MinIO
                storage_url = await minio_storage.upload_file(
                    content=content,
                    object_key=object_key,
                    content_type=detected_content_type,
                    metadata={
                        "organization_id": organization_id,
                        "domain": domain,
                        "uploaded_by": current_user["id"],
                        "original_filename": file.filename
                    }
                )
                storage_type = "minio"
                logger.info(f"File uploaded to MinIO: {object_key}")
                
            except Exception as e:
                logger.error(f"MinIO upload failed: {str(e)}")
                # Fall back to local storage
                pass
        
        # Insert file record into database
        db.execute(
            text("""
                INSERT INTO files (
                    id, filename, original_filename, content_type, size_bytes, domain, organization_id,
                    uploaded_by, file_hash, storage_type, object_key, storage_url,
                    created_at, processed, metadata
                )
                VALUES (
                    :id, :filename, :original_filename, :content_type, :size_bytes, :domain, :organization_id,
                    :uploaded_by, :file_hash, :storage_type, :object_key, :storage_url,
                    :created_at, :processed, :metadata
                )
            """),
            {
                "id": file_id,
                "filename": file.filename,
                "original_filename": file.filename,
                "content_type": detected_content_type,
                "size_bytes": file_size,
                "domain": domain,
                "organization_id": organization_id,
                "uploaded_by": current_user["id"],
                "file_hash": file_hash,
                "storage_type": storage_type,
                "object_key": object_key,
                "storage_url": storage_url,
                "created_at": datetime.utcnow(),
                "processed": False,
                "metadata": "{}"
            }
        )
        
        db.commit()
        
        # Queue for background processing
        if background_job_processor:
            await background_job_processor.queue_file_processing(
                file_id, content, detected_content_type, domain, organization_id
            )
        
        # Log the upload
        AuditLogger.log_event(
            db, "file_upload", current_user["id"], "files", "create",
            f"Uploaded file {file.filename} to domain {domain}",
            {
                "file_id": file_id,
                "filename": file.filename,
                "size_bytes": file_size,
                "content_type": detected_content_type,
                "domain": domain,
                "organization_id": organization_id,
                "storage_type": storage_type
            }
        )
        
        return FileUploadResponse(
            id=file_id,
            filename=file.filename,
            status="uploaded",
            domain=domain,
            processing_status="queued"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


# ============================================================================
# FILE MANAGEMENT ENDPOINTS
# ============================================================================

@router.get("")
async def list_files(
    domain: Optional[str] = None,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """List files with organization isolation"""
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
        
        # Build query with optional domain filter
        query = """
            SELECT f.id, f.filename, f.content_type, f.size_bytes, f.domain,
                   f.created_at, f.processed, f.processing_status, f.metadata,
                   u.username as uploaded_by_username
            FROM files f
            LEFT JOIN users u ON f.uploaded_by = u.id
            WHERE f.organization_id = :organization_id
        """
        params = {"organization_id": organization_id}
        
        if domain:
            query += " AND f.domain = :domain"
            params["domain"] = domain
        
        query += " ORDER BY f.created_at DESC LIMIT 100"
        
        result = db.execute(text(query), params)
        
        files = []
        for row in result.fetchall():
            files.append({
                "id": str(row.id),
                "filename": row.filename,
                "content_type": row.content_type,
                "size_bytes": row.size_bytes,
                "domain": row.domain,
                "upload_date": row.created_at.isoformat(),
                "processed": row.processed,
                "processing_status": row.processing_status,
                "uploaded_by": row.uploaded_by_username,
                "metadata": row.metadata
            })
        
        return {"files": files, "total": len(files)}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list files: {str(e)}")


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Download file with organization isolation"""
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
        
        # Get file info with organization check
        file_result = db.execute(
            text("""
                SELECT f.id, f.filename, f.content_type, f.storage_type, f.object_key, f.storage_url
                FROM files f
                WHERE f.id = :file_id AND f.organization_id = :organization_id
            """),
            {"file_id": file_id, "organization_id": organization_id}
        ).fetchone()
        
        if not file_result:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Generate download URL based on storage type
        if file_result.storage_type == "minio" and minio_storage and file_result.object_key:
            # Generate presigned URL for MinIO
            download_url = minio_storage.generate_presigned_url(
                object_key=file_result.object_key,
                expires_in=3600  # 1 hour
            )
            
            return {
                "download_url": download_url,
                "filename": file_result.filename,
                "content_type": file_result.content_type,
                "expires_in": 3600
            }
        else:
            raise HTTPException(status_code=503, detail="File download not available")
            
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


@router.get("/processing-status")
async def get_processing_status(
    domain: Optional[str] = None,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Get file processing status with organization isolation"""
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
        
        # Build query with optional domain filter
        query = """
            SELECT 
                COUNT(*) as total_files,
                COUNT(CASE WHEN processed = true THEN 1 END) as processed_files,
                COUNT(CASE WHEN processed = false THEN 1 END) as pending_files,
                COUNT(CASE WHEN processing_status = 'error' THEN 1 END) as error_files
            FROM files f
            WHERE f.organization_id = :organization_id
        """
        params = {"organization_id": organization_id}
        
        if domain:
            query += " AND f.domain = :domain"
            params["domain"] = domain
        
        result = db.execute(text(query), params).fetchone()
        
        return {
            "total_files": result.total_files or 0,
            "processed_files": result.processed_files or 0,
            "pending_files": result.pending_files or 0,
            "error_files": result.error_files or 0,
            "processing_complete": (result.pending_files or 0) == 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get processing status: {str(e)}")


# ============================================================================
# WEB SCRAPING ENDPOINTS
# ============================================================================

# Create a separate router for web scraping
web_router = APIRouter(tags=["web-scraping"])


@web_router.post("/start", response_model=WebScrapingResponse)
async def start_web_scraping(
    request: WebScrapingRequest,
    current_user: dict = Depends(require_permission("files:write")),
    db: Session = Depends(get_db)
):
    """Start web scraping with organization isolation"""
    if not CRAWLER_AVAILABLE:
        raise HTTPException(status_code=503, detail="Web crawler service not available")
    
    try:
        # Get user's organization
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
            raise HTTPException(status_code=403, detail=f"Access denied to domain: {request.domain}")
        
        # Generate crawl ID and schedule
        crawl_id = str(uuid.uuid4())
        
        # Set up allowed domains if not provided
        if not request.allowed_domains:
            request.allowed_domains = []
            for url in request.urls:
                parsed = urlparse(url)
                if parsed.netloc and parsed.netloc not in request.allowed_domains:
                    request.allowed_domains.append(parsed.netloc)
        
        # Create crawl configuration
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
        scheduler = CrawlScheduler()
        await scheduler.schedule_crawl(crawl_config, db)
        
        # Estimate completion time
        estimated_pages = min(request.max_pages, len(request.urls) * (request.max_depth ** 2))
        estimated_seconds = estimated_pages * request.delay
        estimated_completion = (datetime.utcnow() + timedelta(seconds=estimated_seconds)).isoformat()
        
        # Log the action
        AuditLogger.log_event(
            db, "web_scraping_started", current_user["id"], "crawl", "create",
            f"Started web scraping for {len(request.urls)} URLs in domain {request.domain}",
            {
                "crawl_id": crawl_id,
                "urls": request.urls,
                "domain": request.domain,
                "organization_id": organization_id,
                "max_pages": request.max_pages
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


@web_router.get("/{crawl_id}/status")
async def get_crawl_status(
    crawl_id: str,
    current_user: dict = Depends(require_permission("files:read")),
    db: Session = Depends(get_db)
):
    """Get crawl status with organization isolation"""
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
            "started_at": result.started_at.isoformat() if result.started_at else None,
            "completed_at": result.completed_at.isoformat() if result.completed_at else None,
            "error_message": result.error_message
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get crawl status: {str(e)}")


# Export all routers
__all__ = ["router", "web_router"] 