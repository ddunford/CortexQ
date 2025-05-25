"""
Background Job Processor for File Processing
Handles document text extraction, embedding generation, and indexing
"""

import asyncio
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
import logging
import os
from pathlib import Path

from sqlalchemy.orm import Session
from sqlalchemy import text
import io

# Optional imports for document processing
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    import docx
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

from database import SessionLocal
# from search.embedding_service import EmbeddingService
# from search.vector_store import MultiDomainVectorStore
# from config import Settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileProcessor:
    """Processes uploaded files into searchable content"""
    
    def __init__(self):
        # self.settings = settings
        # self.embedding_service = EmbeddingService(settings)
        self.vector_store = None
        
    async def initialize(self):
        """Initialize the processor"""
        # await self.embedding_service.initialize()
        # Initialize vector store when needed
        pass
        
    def extract_text_from_file(self, file_path: str, content_type: str, content: bytes) -> str:
        """Extract text from different file types"""
        try:
            if content_type == "application/pdf":
                return self._extract_pdf_text(content)
            elif content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
                return self._extract_docx_text(content)
            elif content_type in ["text/plain", "text/markdown"]:
                return content.decode('utf-8')
            elif content_type == "application/json":
                return content.decode('utf-8')
            else:
                logger.warning(f"Unsupported file type: {content_type}")
                return ""
        except Exception as e:
            logger.error(f"Error extracting text from {content_type}: {e}")
            return ""
    
    def _extract_pdf_text(self, content: bytes) -> str:
        """Extract text from PDF"""
        if not PDF_AVAILABLE:
            logger.warning("PyPDF2 not available, cannot extract PDF text")
            return ""
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting PDF text: {e}")
            return ""
    
    def _extract_docx_text(self, content: bytes) -> str:
        """Extract text from DOCX"""
        if not DOCX_AVAILABLE:
            logger.warning("python-docx not available, cannot extract DOCX text")
            return ""
        try:
            doc_file = io.BytesIO(content)
            doc = docx.Document(doc_file)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except Exception as e:
            logger.error(f"Error extracting DOCX text: {e}")
            return ""
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
        """Split text into overlapping chunks"""
        if len(text) <= chunk_size:
            return [text]
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                # Look for sentence endings
                for i in range(end, max(start + chunk_size - 200, start), -1):
                    if text[i] in '.!?':
                        end = i + 1
                        break
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
            
        return chunks
    
    async def process_file(self, file_id: str, db: Session) -> bool:
        """Process a single file with multi-tenant isolation"""
        try:
            # Get file record with organization context
            file_result = db.execute(
                text("""
                    SELECT f.*, o.slug as org_slug 
                    FROM files f
                    JOIN organizations o ON f.organization_id = o.id
                    WHERE f.id = :file_id
                """),
                {"file_id": file_id}
            ).fetchone()
            
            if not file_result:
                logger.error(f"File {file_id} not found")
                return False
            
            # Verify file path exists and is within organization boundaries
            file_path = Path(file_result.file_path)
            if not file_path.exists():
                logger.error(f"File not found on disk: {file_path}")
                return False
            
            # Security check: ensure file is within organization's storage directory
            storage_base = Path(os.getenv("FILE_STORAGE_PATH", "./uploads"))
            expected_org_path = storage_base / file_result.org_slug
            
            try:
                # Resolve paths to prevent directory traversal attacks
                resolved_file_path = file_path.resolve()
                resolved_org_path = expected_org_path.resolve()
                
                if not str(resolved_file_path).startswith(str(resolved_org_path)):
                    logger.error(f"Security violation: File {file_id} outside organization boundary")
                    return False
            except Exception as e:
                logger.error(f"Path resolution error for file {file_id}: {e}")
                return False
            
            logger.info(f"Processing file: {file_result.original_filename} (Org: {file_result.org_slug}, Domain: {file_result.domain})")
            
            # Read file content from disk
            try:
                with open(file_path, 'rb') as f:
                    file_content = f.read()
            except Exception as e:
                logger.error(f"Failed to read file {file_path}: {e}")
                return False
            
            # Extract text based on content type
            text_content = self.extract_text_from_file(
                str(file_path), 
                file_result.content_type, 
                file_content
            )
            
            if not text_content.strip():
                logger.warning(f"No text content extracted from {file_result.original_filename}")
                # Still mark as processed to avoid infinite retries
                db.execute(
                    text("""
                        UPDATE files 
                        SET processed = true, processing_status = 'completed', 
                            processing_error = 'No text content extracted', updated_at = :updated_at
                        WHERE id = :file_id
                    """),
                    {
                        "file_id": file_id,
                        "updated_at": datetime.utcnow()
                    }
                )
                db.commit()
                return True
            
            # Chunk the text
            chunks = self.chunk_text(text_content)
            logger.info(f"Created {len(chunks)} chunks from {file_result.original_filename}")
            
            # Generate embeddings for each chunk with organization isolation
            for i, chunk in enumerate(chunks):
                try:
                    # TODO: Replace with actual embedding service call
                    # embedding = await self.embedding_service.generate_embedding(chunk)
                    # For now, create a mock embedding
                    embedding = [0.1] * 384  # Mock 384-dimensional embedding
                    
                    # Store embedding with organization and domain context
                    embedding_id = str(uuid.uuid4())
                    db.execute(
                        text("""
                            INSERT INTO embeddings (
                                id, source_id, source_type, domain, organization_id, chunk_index,
                                content_text, embedding, created_at
                            ) VALUES (
                                :id, :source_id, :source_type, :domain, :organization_id, :chunk_index,
                                :content_text, :embedding, :created_at
                            )
                        """),
                        {
                            "id": embedding_id,
                            "source_id": file_id,
                            "source_type": "file",
                            "domain": file_result.domain,
                            "organization_id": file_result.organization_id,
                            "chunk_index": i,
                            "content_text": chunk,
                            "embedding": embedding,
                            "created_at": datetime.utcnow()
                        }
                    )
                    
                except Exception as e:
                    logger.error(f"Error processing chunk {i} for file {file_id}: {e}")
                    continue
            
            # Update file status
            db.execute(
                text("""
                    UPDATE files 
                    SET processed = true, processing_status = 'completed', updated_at = :updated_at
                    WHERE id = :file_id
                """),
                {
                    "file_id": file_id,
                    "updated_at": datetime.utcnow()
                }
            )
            
            db.commit()
            logger.info(f"Successfully processed file: {file_result.original_filename} (Org: {file_result.org_slug})")
            return True
            
        except Exception as e:
            logger.error(f"Error processing file {file_id}: {e}")
            db.rollback()
            
            # Update job status to failed
            db.execute(
                text("""
                    UPDATE files 
                    SET processing_status = 'failed', processing_error = :error_message, updated_at = :updated_at
                    WHERE id = :file_id
                """),
                {
                    "file_id": file_id,
                    "error_message": str(e),
                    "updated_at": datetime.utcnow()
                }
            )
            db.commit()
            return False


class BackgroundJobProcessor:
    """Background job processor for handling file processing tasks"""
    
    def __init__(self):
        # self.settings = settings
        self.file_processor = FileProcessor()
        self.running = False
        
    async def initialize(self):
        """Initialize the processor"""
        await self.file_processor.initialize()
        
    async def start(self):
        """Start the background job processor"""
        self.running = True
        logger.info("Background job processor started")
        
        while self.running:
            try:
                await self.process_pending_jobs()
                await asyncio.sleep(5)  # Check for new jobs every 5 seconds
            except Exception as e:
                logger.error(f"Error in background processor: {e}")
                await asyncio.sleep(10)  # Wait longer on error
    
    def stop(self):
        """Stop the background job processor"""
        self.running = False
        logger.info("Background job processor stopped")
    
    async def process_pending_jobs(self):
        """Process pending file processing jobs with multi-tenant isolation"""
        db = SessionLocal()
        try:
            # Get pending jobs with organization context
            pending_jobs = db.execute(
                text("""
                    SELECT fpj.id, fpj.file_id, fpj.job_type, fpj.attempts, fpj.organization_id, fpj.domain,
                           f.original_filename, o.slug as org_slug
                    FROM file_processing_jobs fpj
                    JOIN files f ON fpj.file_id = f.id
                    JOIN organizations o ON fpj.organization_id = o.id
                    WHERE fpj.status = 'pending' 
                    AND fpj.attempts < fpj.max_attempts
                    AND o.is_active = true
                    ORDER BY fpj.created_at ASC
                    LIMIT 10
                """)
            ).fetchall()
            
            for job in pending_jobs:
                logger.info(f"Processing job {job.id} for file {job.original_filename} (Org: {job.org_slug}, Domain: {job.domain})")
                await self.process_job(job, db)
                
        except Exception as e:
            logger.error(f"Error processing pending jobs: {e}")
        finally:
            db.close()
    
    async def process_job(self, job, db: Session):
        """Process a single job"""
        job_id = job.id
        file_id = job.file_id
        
        try:
            # Update job status to running
            db.execute(
                text("""
                    UPDATE file_processing_jobs 
                    SET status = 'running', started_at = :started_at, attempts = attempts + 1
                    WHERE id = :job_id
                """),
                {
                    "job_id": job_id,
                    "started_at": datetime.utcnow()
                }
            )
            db.commit()
            
            # Process the file
            success = await self.file_processor.process_file(file_id, db)
            
            if success:
                # Mark job as completed
                db.execute(
                    text("""
                        UPDATE file_processing_jobs 
                        SET status = 'completed', completed_at = :completed_at
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "completed_at": datetime.utcnow()
                    }
                )
            else:
                # Mark job as failed
                db.execute(
                    text("""
                        UPDATE file_processing_jobs 
                        SET status = 'failed', completed_at = :completed_at,
                            error_message = 'File processing failed'
                        WHERE id = :job_id
                    """),
                    {
                        "job_id": job_id,
                        "completed_at": datetime.utcnow()
                    }
                )
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Error processing job {job_id}: {e}")
            
            # Mark job as failed
            db.execute(
                text("""
                    UPDATE file_processing_jobs 
                    SET status = 'failed', completed_at = :completed_at,
                        error_message = :error_message
                    WHERE id = :job_id
                """),
                {
                    "job_id": job_id,
                    "completed_at": datetime.utcnow(),
                    "error_message": str(e)
                }
            )
            db.commit()


# Global processor instance
background_processor = None

async def start_background_processor():
    """Start the background processor"""
    global background_processor
    # from config import get_settings
    
    # settings = get_settings()
    background_processor = BackgroundJobProcessor()
    await background_processor.initialize()
    await background_processor.start()

def stop_background_processor():
    """Stop the background processor"""
    global background_processor
    if background_processor:
        background_processor.stop() 