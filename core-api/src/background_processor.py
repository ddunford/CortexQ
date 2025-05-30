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
import json

from sqlalchemy.orm import Session
from sqlalchemy import text
import io

# Optional imports for document processing
try:
    import pypdf
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
        self.embeddings_service = None
        
    async def initialize(self):
        """Initialize the processor"""
        try:
            # Use the centralized embeddings service
            from embeddings_service import get_embeddings_service
            self.embeddings_service = get_embeddings_service()
            if self.embeddings_service.is_available():
                logger.info("Background processor initialized with embeddings service")
            else:
                logger.warning("Embeddings service not available")
        except ImportError as e:
            logger.warning(f"Could not import embeddings service: {e}")
            self.embeddings_service = None
        
        # Initialize visual content extractor
        try:
            from ingestion.visual_extractor import VisualContentExtractor
            self.visual_extractor = VisualContentExtractor()
            logger.info("Visual content extractor initialized")
        except ImportError as e:
            logger.warning(f"Could not import visual extractor: {e}")
            self.visual_extractor = None
        
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
            logger.warning("pypdf not available, cannot extract PDF text")
            return ""
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = pypdf.PdfReader(pdf_file)
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
        """Process a single file with multi-tenant isolation and MinIO support"""
        try:
            # Get file record with organization context
            file_result = db.execute(
                text("""
                    SELECT f.*, o.slug as org_slug, od.domain_name as domain
                    FROM files f
                    JOIN organizations o ON f.organization_id = o.id
                    JOIN organization_domains od ON f.domain_id = od.id
                    WHERE f.id = :file_id
                """),
                {"file_id": file_id}
            ).fetchone()
            
            if not file_result:
                logger.error(f"File {file_id} not found")
                return False
            
            logger.info(f"Processing file: {file_result.original_filename} (Org: {file_result.org_slug}, Domain: {file_result.domain})")
            
            # Get file content from storage
            try:
                if file_result.storage_type == 'minio' and file_result.object_key:
                    # Download file content from MinIO
                    from storage_utils import minio_storage
                    file_content = minio_storage.download_file(file_result.object_key)
                    if not file_content:
                        logger.error(f"Failed to download file from MinIO: {file_result.object_key}")
                        return False
                elif file_result.storage_type == 'local' and file_result.file_path:
                    # Read file from local storage
                    file_path = Path(file_result.file_path)
                    if not file_path.exists():
                        logger.error(f"Local file not found: {file_path}")
                        return False
                    
                    with open(file_path, 'rb') as f:
                        file_content = f.read()
                else:
                    # Legacy fallback - try object_key as file path
                    if file_result.object_key:
                        file_path = Path(file_result.object_key)
                        if file_path.exists():
                            with open(file_path, 'rb') as f:
                                file_content = f.read()
                        else:
                            logger.error(f"Neither MinIO object nor local file found for {file_id}")
                            return False
                    else:
                        logger.error(f"No storage location found for file {file_id}")
                        return False
                        
            except Exception as e:
                logger.error(f"Failed to read file content for {file_id}: {e}")
                return False
            
            # Extract text based on content type
            text_content = self.extract_text_from_file(
                file_result.object_key or file_result.file_path, 
                file_result.content_type, 
                file_content
            )
            
            # Extract visual content (images, screenshots)
            visual_content = {}
            if self.visual_extractor:
                try:
                    visual_content = self.visual_extractor.extract_visual_content(
                        file_content, 
                        file_result.content_type, 
                        file_result.original_filename
                    )
                    logger.info(f"Extracted {len(visual_content.get('images', []))} images and {len(visual_content.get('screenshots', []))} screenshots from {file_result.original_filename}")
                except Exception as e:
                    logger.warning(f"Failed to extract visual content from {file_result.original_filename}: {e}")
                    visual_content = {"images": [], "screenshots": [], "has_visual_content": False}
            
            if not text_content.strip():
                # Update metadata even if no text content
                updated_metadata = {
                    **(json.loads(file_result.metadata) if file_result.metadata else {}),
                    "visual_content": visual_content,
                    "processing_completed_at": datetime.utcnow().isoformat()
                }
                
                logger.warning(f"No text content extracted from {file_result.original_filename}")
                # Still mark as processed to avoid infinite retries
                db.execute(
                    text("""
                        UPDATE files 
                        SET processed = true, processing_status = 'completed', 
                            processing_error = 'No text content extracted', 
                            metadata = :metadata, updated_at = :updated_at
                        WHERE id = :file_id
                    """),
                    {
                        "file_id": file_id,
                        "metadata": json.dumps(updated_metadata),
                        "updated_at": datetime.utcnow()
                    }
                )
                db.commit()
                return True
            
            # Chunk the text
            chunks = self.chunk_text(text_content)
            logger.info(f"Created {len(chunks)} chunks from {file_result.original_filename}")
            
            # Generate embeddings for each chunk
            embedding_records = []
            for i, chunk in enumerate(chunks):
                try:
                    if self.embeddings_service and self.embeddings_service.is_available():
                        embedding = self.embeddings_service.generate_embedding(chunk)
                        if embedding is not None:
                            # Enhanced metadata including visual content for relevant chunks
                            chunk_metadata = {
                                "title": file_result.original_filename,
                                "content_type": file_result.content_type,
                                "chunk_index": i,
                                "chunk_size": len(chunk),
                                "word_count": len(chunk.split()),
                                "domain": file_result.domain,
                                "organization_id": str(file_result.organization_id),
                                "uploaded_by": str(file_result.uploaded_by),
                                "file_size": file_result.size_bytes,
                                "upload_date": file_result.created_at.isoformat()
                            }
                            
                            # Add visual content info if available
                            if visual_content.get("has_visual_content"):
                                chunk_metadata.update({
                                    "has_images": len(visual_content.get("images", [])) > 0,
                                    "has_screenshots": len(visual_content.get("screenshots", [])) > 0,
                                    "image_count": len(visual_content.get("images", [])),
                                    "screenshot_count": len(visual_content.get("screenshots", [])),
                                    "visual_content_summary": f"{len(visual_content.get('images', []))} images, {len(visual_content.get('screenshots', []))} screenshots"
                                })
                                
                                # For the first chunk, include actual visual content for search results
                                if i == 0:
                                    chunk_metadata["images"] = visual_content.get("images", [])
                                    chunk_metadata["screenshots"] = visual_content.get("screenshots", [])
                            
                            embedding_records.append({
                                "embedding": embedding.tolist(),
                                "content_text": chunk,
                                "metadata": chunk_metadata
                            })
                    else:
                        logger.warning(f"Embeddings service not available for chunk {i}")
                    
                except Exception as e:
                    logger.error(f"Failed to generate embedding for chunk {i}: {e}")
                    continue
            
            # Store embeddings in the database
            for record in embedding_records:
                try:
                    embedding_id = str(uuid.uuid4())
                    db.execute(
                        text("""
                            INSERT INTO embeddings (
                                id, source_id, domain_id, organization_id, chunk_index, 
                                content_text, embedding, created_at
                            ) VALUES (
                                :id, :source_id, :domain_id, :organization_id, :chunk_index,
                                :content_text, :embedding, :created_at
                            )
                        """),
                        {
                            "id": embedding_id,
                            "source_id": file_id,
                            "domain_id": file_result.domain_id,
                            "organization_id": file_result.organization_id,
                            "chunk_index": record["metadata"]["chunk_index"],
                            "content_text": record["content_text"],
                            "embedding": json.dumps(record["embedding"]),
                            "created_at": datetime.utcnow()
                        }
                    )
                except Exception as e:
                    logger.error(f"Error storing embedding: {e}")
            
            # Update file status and metadata with visual content
            final_metadata = {
                **(json.loads(file_result.metadata) if file_result.metadata else {}),
                "processing_completed_at": datetime.utcnow().isoformat(),
                "chunks_created": len(chunks),
                "embeddings_created": len(embedding_records),
                "visual_content": visual_content,
                "text_length": len(text_content),
                "word_count": len(text_content.split())
            }
            
            db.execute(
                text("""
                    UPDATE files 
                    SET processed = true, processing_status = 'completed', 
                        metadata = :metadata, updated_at = :updated_at
                    WHERE id = :file_id
                """),
                {
                    "file_id": file_id,
                    "metadata": json.dumps(final_metadata),
                    "updated_at": datetime.utcnow()
                }
            )
            
            db.commit()
            logger.info(f"Successfully processed file: {file_result.original_filename} (Org: {file_result.org_slug})")
            
            # Smart cache update for this domain since new embeddings were generated
            try:
                # Import here to avoid circular imports
                from main import rag_processor
                if rag_processor:
                    # Use smart cache update instead of full invalidation
                    await rag_processor.smart_cache_update_for_new_content(
                        domain=file_result.domain,
                        new_file_id=str(file_result.id),
                        new_content_chunks=chunks,
                        db=db
                    )
                    logger.info(f"Smart cache update completed for domain '{file_result.domain}' after processing file {file_result.original_filename}")
            except Exception as e:
                logger.warning(f"Failed to update cache after file processing: {e}")
                # Fallback to domain invalidation if smart update fails
                try:
                    if rag_processor:
                        rag_processor.invalidate_cache_for_domain(file_result.domain)
                        logger.info(f"Fallback: Cache invalidated for domain '{file_result.domain}'")
                except:
                    pass
            
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
                    SELECT fpj.id, fpj.file_id, fpj.job_type, fpj.attempts, fpj.organization_id, fpj.domain_id,
                           f.original_filename, o.slug as org_slug, od.domain_name as domain
                    FROM file_processing_jobs fpj
                    JOIN files f ON fpj.file_id = f.id
                    JOIN organizations o ON fpj.organization_id = o.id
                    JOIN organization_domains od ON fpj.domain_id = od.id
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

    async def queue_file_processing(self, file_id: str, content: bytes, content_type: str, domain: str, organization_id: str):
        """Queue a file for processing by creating a job record"""
        db = SessionLocal()
        try:
            # Get domain_id from domain name
            domain_result = db.execute(
                text("""
                    SELECT id FROM organization_domains 
                    WHERE organization_id = :organization_id AND domain_name = :domain_name AND is_active = true
                """),
                {"organization_id": organization_id, "domain_name": domain}
            ).fetchone()
            
            if not domain_result:
                logger.error(f"Domain '{domain}' not found for organization {organization_id}")
                return False
            
            domain_id = str(domain_result.id)
            
            # Create processing job
            job_id = str(uuid.uuid4())
            db.execute(
                text("""
                    INSERT INTO file_processing_jobs (
                        id, file_id, job_type, status, attempts, max_attempts,
                        organization_id, domain_id, created_at, updated_at
                    ) VALUES (
                        :id, :file_id, :job_type, :status, :attempts, :max_attempts,
                        :organization_id, :domain_id, :created_at, :updated_at
                    )
                """),
                {
                    "id": job_id,
                    "file_id": file_id,
                    "job_type": "file_processing",
                    "status": "pending",
                    "attempts": 0,
                    "max_attempts": 3,
                    "organization_id": organization_id,
                    "domain_id": domain_id,
                    "created_at": datetime.utcnow(),
                    "updated_at": datetime.utcnow()
                }
            )
            
            db.commit()
            logger.info(f"Queued file processing job {job_id} for file {file_id} in domain {domain}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to queue file processing for {file_id}: {e}")
            db.rollback()
            return False
        finally:
            db.close()


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


# Task Status and Priority Enums for tests
class TaskStatus:
    """Task status enumeration"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority:
    """Task priority enumeration"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class BackgroundProcessor:
    """Background processor for compatibility with tests"""
    
    def __init__(self, max_workers: int = 4, queue_size: int = 100, retry_attempts: int = 3, retry_delay: float = 1.0):
        self.max_workers = max_workers
        self.queue_size = queue_size
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.is_running = False
        self.workers = []
        self.task_queue = asyncio.Queue(maxsize=queue_size)
        self.tasks = {}
        
    async def start(self):
        """Start the background processor"""
        if self.is_running:
            return
        
        self.is_running = True
        self.workers = []
        
        # Start worker tasks
        for i in range(self.max_workers):
            worker = asyncio.create_task(self._worker(f"worker-{i}"))
            self.workers.append(worker)
    
    async def stop(self):
        """Stop the background processor"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        # Cancel all workers
        for worker in self.workers:
            worker.cancel()
        
        # Wait for workers to finish
        await asyncio.gather(*self.workers, return_exceptions=True)
        self.workers = []
    
    async def add_task(self, task_type: str, task_data: dict, priority: str = TaskPriority.NORMAL) -> str:
        """Add a task to the queue"""
        task_id = str(uuid.uuid4())
        task = {
            "id": task_id,
            "type": task_type,
            "data": task_data,
            "priority": priority,
            "status": TaskStatus.PENDING,
            "created_at": datetime.utcnow(),
            "retry_count": 0
        }
        
        self.tasks[task_id] = task
        
        try:
            await self.task_queue.put(task)
            return task_id
        except asyncio.QueueFull:
            del self.tasks[task_id]
            raise Exception("Task queue is full")
    
    async def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get task status"""
        return self.tasks.get(task_id)
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a task"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task["status"] in [TaskStatus.PENDING, TaskStatus.RUNNING]:
            task["status"] = TaskStatus.CANCELLED
            return True
        
        return False
    
    async def _worker(self, worker_name: str):
        """Worker coroutine to process tasks"""
        while self.is_running:
            try:
                # Get task from queue with timeout
                task = await asyncio.wait_for(self.task_queue.get(), timeout=1.0)
                
                if task["status"] == TaskStatus.CANCELLED:
                    continue
                
                # Process the task
                task["status"] = TaskStatus.RUNNING
                
                try:
                    await self._process_task(task)
                    task["status"] = TaskStatus.COMPLETED
                except Exception as e:
                    task["status"] = TaskStatus.FAILED
                    task["error"] = str(e)
                
            except asyncio.TimeoutError:
                # No task available, continue
                continue
            except Exception as e:
                logger.error(f"Worker {worker_name} error: {e}")
    
    async def _process_task(self, task: dict):
        """Process a single task"""
        task_type = task["type"]
        task_data = task["data"]
        
        if task_type == "file_processing":
            await self._process_file_task(task_data)
        elif task_type == "web_scraping":
            await self._process_web_scraping_task(task_data)
        elif task_type == "embedding_generation":
            await self._process_embedding_task(task_data)
        else:
            raise ValueError(f"Unknown task type: {task_type}")
    
    async def _process_file_task(self, task_data: dict):
        """Process file task"""
        # Mock implementation for testing
        await asyncio.sleep(0.1)  # Simulate processing time
        return {"result": "file processed"}
    
    async def _process_web_scraping_task(self, task_data: dict):
        """Process web scraping task"""
        # Mock implementation for testing
        await asyncio.sleep(0.1)  # Simulate processing time
        return {"result": "web content scraped"}
    
    async def _process_embedding_task(self, task_data: dict):
        """Process embedding generation task"""
        # Mock implementation for testing
        await asyncio.sleep(0.1)  # Simulate processing time
        return {"result": "embeddings generated"} 