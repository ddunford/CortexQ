"""
MinIO Storage Utilities
Provides S3-compatible object storage for uploaded documents with organization isolation
"""

import os
import uuid
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, BinaryIO
from urllib.parse import urlparse

from minio import Minio
from minio.error import S3Error
from minio.commonconfig import Tags

logger = logging.getLogger(__name__)


class MinIOStorageManager:
    """MinIO storage manager with organization isolation"""
    
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin123")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        
        # Initialize MinIO client
        self.client = Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
        
        # Default bucket for documents
        self.documents_bucket = "rag-documents"
        
        # Initialize buckets
        self._ensure_buckets_exist()
    
    def _ensure_buckets_exist(self):
        """Ensure required buckets exist"""
        try:
            # Create documents bucket if it doesn't exist
            if not self.client.bucket_exists(self.documents_bucket):
                self.client.make_bucket(self.documents_bucket)
                logger.info(f"Created bucket: {self.documents_bucket}")
                
                # Set bucket policy for organization isolation
                self._set_bucket_policy(self.documents_bucket)
                
        except S3Error as e:
            logger.error(f"Error creating buckets: {e}")
    
    def _set_bucket_policy(self, bucket_name: str):
        """Set bucket policy for organization isolation"""
        # Basic policy - in production, you'd want more sophisticated policies
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Principal": {"AWS": ["*"]},
                    "Action": ["s3:GetObject"],
                    "Resource": [f"arn:aws:s3:::{bucket_name}/*"]
                }
            ]
        }
        
        try:
            import json
            self.client.set_bucket_policy(bucket_name, json.dumps(policy))
        except S3Error as e:
            logger.warning(f"Could not set bucket policy: {e}")
    
    def generate_object_key(
        self, 
        organization_slug: str, 
        domain: str, 
        file_id: str, 
        filename: str
    ) -> str:
        """Generate object key with organization isolation"""
        # Structure: org_slug/domain/year/month/file_id/filename
        now = datetime.utcnow()
        year = now.strftime("%Y")
        month = now.strftime("%m")
        
        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in ".-_")
        
        return f"{organization_slug}/{domain}/{year}/{month}/{file_id}/{safe_filename}"
    
    async def upload_file(
        self,
        file_content: bytes,
        organization_slug: str,
        domain: str,
        file_id: str,
        filename: str,
        content_type: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """Upload file to MinIO with organization isolation"""
        try:
            object_key = self.generate_object_key(organization_slug, domain, file_id, filename)
            
            # Prepare metadata
            file_metadata = {
                "organization": organization_slug,
                "domain": domain,
                "file_id": file_id,
                "original_filename": filename,
                "upload_date": datetime.utcnow().isoformat(),
                "content_type": content_type
            }
            
            if metadata:
                file_metadata.update(metadata)
            
            # Upload file
            from io import BytesIO
            file_stream = BytesIO(file_content)
            
            result = self.client.put_object(
                bucket_name=self.documents_bucket,
                object_name=object_key,
                data=file_stream,
                length=len(file_content),
                content_type=content_type,
                metadata=file_metadata
            )
            
            logger.info(f"Uploaded file {filename} to MinIO: {object_key}")
            
            return {
                "success": True,
                "object_key": object_key,
                "bucket": self.documents_bucket,
                "etag": result.etag,
                "size": len(file_content),
                "url": self.get_file_url(object_key)
            }
            
        except S3Error as e:
            logger.error(f"Error uploading file to MinIO: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_file_url(self, object_key: str, expires: timedelta = timedelta(hours=1)) -> str:
        """Get presigned URL for file access"""
        try:
            url = self.client.presigned_get_object(
                bucket_name=self.documents_bucket,
                object_name=object_key,
                expires=expires
            )
            return url
        except S3Error as e:
            logger.error(f"Error generating presigned URL: {e}")
            return ""
    
    def generate_presigned_url(self, object_key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for file access (alias for get_file_url)"""
        expires = timedelta(seconds=expires_in)
        return self.get_file_url(object_key, expires)
    
    def download_file(self, object_key: str) -> Optional[bytes]:
        """Download file from MinIO"""
        try:
            response = self.client.get_object(
                bucket_name=self.documents_bucket,
                object_name=object_key
            )
            
            content = response.read()
            response.close()
            response.release_conn()
            
            return content
            
        except S3Error as e:
            logger.error(f"Error downloading file from MinIO: {e}")
            return None
    
    def delete_file(self, object_key: str) -> bool:
        """Delete file from MinIO"""
        try:
            self.client.remove_object(
                bucket_name=self.documents_bucket,
                object_name=object_key
            )
            logger.info(f"Deleted file from MinIO: {object_key}")
            return True
            
        except S3Error as e:
            logger.error(f"Error deleting file from MinIO: {e}")
            return False
    
    def list_organization_files(
        self, 
        organization_slug: str, 
        domain: Optional[str] = None,
        prefix: Optional[str] = None
    ) -> list:
        """List files for an organization with optional domain filter"""
        try:
            # Build prefix for organization isolation
            if domain:
                search_prefix = f"{organization_slug}/{domain}/"
            else:
                search_prefix = f"{organization_slug}/"
            
            if prefix:
                search_prefix += prefix
            
            objects = self.client.list_objects(
                bucket_name=self.documents_bucket,
                prefix=search_prefix,
                recursive=True
            )
            
            files = []
            for obj in objects:
                try:
                    # Get object metadata
                    stat = self.client.stat_object(
                        bucket_name=self.documents_bucket,
                        object_name=obj.object_name
                    )
                    
                    files.append({
                        "object_key": obj.object_name,
                        "size": obj.size,
                        "last_modified": obj.last_modified,
                        "etag": obj.etag,
                        "metadata": stat.metadata,
                        "content_type": stat.content_type
                    })
                except S3Error:
                    # Skip objects we can't access
                    continue
            
            return files
            
        except S3Error as e:
            logger.error(f"Error listing files for organization {organization_slug}: {e}")
            return []
    
    def get_file_info(self, object_key: str) -> Optional[Dict[str, Any]]:
        """Get file information and metadata"""
        try:
            stat = self.client.stat_object(
                bucket_name=self.documents_bucket,
                object_name=object_key
            )
            
            return {
                "object_key": object_key,
                "size": stat.size,
                "last_modified": stat.last_modified,
                "etag": stat.etag,
                "content_type": stat.content_type,
                "metadata": stat.metadata
            }
            
        except S3Error as e:
            logger.error(f"Error getting file info: {e}")
            return None
    
    def check_organization_access(self, object_key: str, organization_slug: str) -> bool:
        """Verify that an object belongs to the specified organization"""
        # Simple check: object key should start with organization slug
        return object_key.startswith(f"{organization_slug}/")
    
    def get_storage_stats(self, organization_slug: str) -> Dict[str, Any]:
        """Get storage statistics for an organization"""
        try:
            files = self.list_organization_files(organization_slug)
            
            total_size = sum(f["size"] for f in files)
            file_count = len(files)
            
            # Group by domain
            domains = {}
            for file in files:
                parts = file["object_key"].split("/")
                if len(parts) >= 2:
                    domain = parts[1]
                    if domain not in domains:
                        domains[domain] = {"count": 0, "size": 0}
                    domains[domain]["count"] += 1
                    domains[domain]["size"] += file["size"]
            
            return {
                "total_files": file_count,
                "total_size": total_size,
                "domains": domains,
                "organization": organization_slug
            }
            
        except Exception as e:
            logger.error(f"Error getting storage stats: {e}")
            return {
                "total_files": 0,
                "total_size": 0,
                "domains": {},
                "organization": organization_slug
            }


# Global instance
minio_storage = MinIOStorageManager() 