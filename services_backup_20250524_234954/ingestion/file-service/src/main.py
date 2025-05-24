"""
File Ingestion Service
Handles file uploads, parsing, and metadata extraction for the RAG system.
"""

import os
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import uvicorn
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import aiofiles

from config import get_settings
from database import get_db, FileRecord
from utils import get_file_hash, detect_content_type, validate_file_type

# Initialize FastAPI app
app = FastAPI(
    title="File Ingestion Service",
    description="Handles file uploads and processing for the RAG searcher",
    version="0.1.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class FileUploadResponse(BaseModel):
    id: str
    filename: str
    content_type: str
    size: int
    status: str
    upload_date: datetime

class FileInfo(BaseModel):
    id: str
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    file_hash: str
    processed: bool
    processing_status: str
    metadata: dict
    upload_date: datetime

class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
    version: str

# Get settings
settings = get_settings()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        service="file-ingestion",
        timestamp=datetime.utcnow(),
        version="0.1.0"
    )

@app.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    db = Depends(get_db)
):
    """
    Upload a file for processing
    """
    try:
        # Validate file type
        if not validate_file_type(file.filename):
            raise HTTPException(
                status_code=400,
                detail=f"File type not supported. Allowed types: {settings.ALLOWED_FILE_TYPES}"
            )
        
        # Check file size
        content = await file.read()
        file_size = len(content)
        max_size = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        
        if file_size > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB"
            )
        
        # Generate file hash
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check if file already exists
        existing_file = db.query(FileRecord).filter(FileRecord.file_hash == file_hash).first()
        if existing_file:
            return FileUploadResponse(
                id=str(existing_file.id),
                filename=existing_file.filename,
                content_type=existing_file.content_type,
                size=existing_file.size_bytes,
                status="already_exists",
                upload_date=existing_file.upload_date
            )
        
        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_extension = Path(file.filename).suffix
        unique_filename = f"{file_id}{file_extension}"
        
        # Create upload directory if it doesn't exist
        upload_dir = Path(settings.FILE_STORAGE_PATH)
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        file_path = upload_dir / unique_filename
        async with aiofiles.open(file_path, 'wb') as f:
            await f.write(content)
        
        # Detect content type
        content_type = detect_content_type(file.filename, content)
        
        # Create database record
        file_record = FileRecord(
            id=uuid.UUID(file_id),
            filename=unique_filename,
            original_filename=file.filename,
            content_type=content_type,
            size_bytes=file_size,
            file_hash=file_hash,
            processed=False,
            processing_status="pending",
            file_metadata={"file_path": str(file_path)},
            upload_date=datetime.utcnow()
        )
        
        db.add(file_record)
        db.commit()
        db.refresh(file_record)
        
        return FileUploadResponse(
            id=str(file_record.id),
            filename=file_record.original_filename,
            content_type=file_record.content_type,
            size=file_record.size_bytes,
            status="uploaded",
            upload_date=file_record.upload_date
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

@app.get("/files/{file_id}", response_model=FileInfo)
async def get_file_info(file_id: str, db = Depends(get_db)):
    """
    Get file information by ID
    """
    try:
        file_uuid = uuid.UUID(file_id)
        file_record = db.query(FileRecord).filter(FileRecord.id == file_uuid).first()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        return FileInfo(
            id=str(file_record.id),
            filename=file_record.filename,
            original_filename=file_record.original_filename,
            content_type=file_record.content_type,
            size_bytes=file_record.size_bytes,
            file_hash=file_record.file_hash,
            processed=file_record.processed,
            processing_status=file_record.processing_status,
            metadata=file_record.file_metadata,
            upload_date=file_record.upload_date
        )
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving file: {str(e)}")

@app.delete("/files/{file_id}")
async def delete_file(file_id: str, db = Depends(get_db)):
    """
    Delete a file by ID
    """
    try:
        file_uuid = uuid.UUID(file_id)
        file_record = db.query(FileRecord).filter(FileRecord.id == file_uuid).first()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        # Delete physical file
        if "file_path" in file_record.file_metadata:
            file_path = Path(file_record.file_metadata["file_path"])
            if file_path.exists():
                file_path.unlink()
        
        # Delete database record
        db.delete(file_record)
        db.commit()
        
        return {"message": "File deleted successfully", "file_id": file_id}
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error deleting file: {str(e)}")

@app.post("/process/{file_id}")
async def process_file(file_id: str, domain: str = "general", db = Depends(get_db)):
    """
    Process a file for indexing and embedding generation
    """
    try:
        file_uuid = uuid.UUID(file_id)
        file_record = db.query(FileRecord).filter(FileRecord.id == file_uuid).first()
        
        if not file_record:
            raise HTTPException(status_code=404, detail="File not found")
        
        if file_record.processed:
            return {
                "message": "File already processed",
                "file_id": file_id,
                "status": "already_processed"
            }
        
        # Update processing status
        file_record.processing_status = "processing"
        db.commit()
        
        # Here you would typically:
        # 1. Extract text from the file
        # 2. Chunk the content
        # 3. Generate embeddings
        # 4. Store in vector database
        
        # For now, we'll simulate processing
        file_record.processed = True
        file_record.processing_status = "completed"
        file_record.file_metadata["domain"] = domain
        file_record.file_metadata["processed_at"] = datetime.utcnow().isoformat()
        
        db.commit()
        
        return {
            "message": "File processing completed",
            "file_id": file_id,
            "status": "completed",
            "domain": domain
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid file ID format")
    except Exception as e:
        db.rollback()
        # Update status to failed
        try:
            file_record.processing_status = "failed"
            db.commit()
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@app.get("/files")
async def list_files(
    skip: int = 0,
    limit: int = 100,
    processed: Optional[bool] = None,
    db = Depends(get_db)
):
    """
    List uploaded files with pagination
    """
    query = db.query(FileRecord)
    
    if processed is not None:
        query = query.filter(FileRecord.processed == processed)
    
    files = query.offset(skip).limit(limit).all()
    
    return {
        "files": [
            {
                "id": str(f.id),
                "filename": f.original_filename,
                "content_type": f.content_type,
                "size_bytes": f.size_bytes,
                "processed": f.processed,
                "processing_status": f.processing_status,
                "upload_date": f.upload_date
            }
            for f in files
        ],
        "total": query.count(),
        "skip": skip,
        "limit": limit
    }

if __name__ == "__main__":
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=int(os.getenv("FILE_SERVICE_PORT", 8001)),
        reload=False
    ) 