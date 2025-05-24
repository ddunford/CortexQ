"""
Utility functions for the File Ingestion Service
"""

import hashlib
import mimetypes
from pathlib import Path
from typing import Optional

from config import get_settings

settings = get_settings()


def get_file_hash(content: bytes) -> str:
    """
    Generate SHA-256 hash of file content
    """
    return hashlib.sha256(content).hexdigest()


def validate_file_type(filename: str) -> bool:
    """
    Validate if file type is allowed
    """
    if not filename:
        return False
    
    file_extension = Path(filename).suffix.lower().lstrip('.')
    allowed_extensions = settings.allowed_file_extensions
    
    return file_extension in allowed_extensions


def detect_content_type(filename: str, content: bytes = None) -> str:
    """
    Detect content type based on filename and content
    """
    # First, try to guess from filename
    content_type, _ = mimetypes.guess_type(filename)
    
    if content_type:
        return content_type
    
    # Fallback based on file extension
    file_extension = Path(filename).suffix.lower()
    
    extension_map = {
        '.pdf': 'application/pdf',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.doc': 'application/msword',
        '.txt': 'text/plain',
        '.md': 'text/markdown',
        '.json': 'application/json',
        '.csv': 'text/csv',
        '.yaml': 'application/x-yaml',
        '.yml': 'application/x-yaml',
        '.py': 'text/x-python',
        '.js': 'application/javascript',
        '.java': 'text/x-java-source',
        '.cpp': 'text/x-c++src',
        '.c': 'text/x-csrc',
        '.h': 'text/x-chdr',
        '.html': 'text/html',
        '.xml': 'application/xml',
        '.zip': 'application/zip',
        '.tar': 'application/x-tar',
        '.gz': 'application/gzip'
    }
    
    return extension_map.get(file_extension, 'application/octet-stream')


def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024.0 and i < len(size_names) - 1:
        size /= 1024.0
        i += 1
    
    return f"{size:.1f} {size_names[i]}"


def is_text_file(content_type: str) -> bool:
    """
    Check if file is a text file
    """
    text_types = [
        'text/',
        'application/json',
        'application/xml',
        'application/javascript',
        'application/x-yaml'
    ]
    
    return any(content_type.startswith(t) for t in text_types)


def extract_text_preview(content: bytes, max_length: int = 500) -> Optional[str]:
    """
    Extract text preview from file content
    """
    try:
        # Try to decode as UTF-8
        text = content.decode('utf-8')
        if len(text) > max_length:
            return text[:max_length] + "..."
        return text
    except UnicodeDecodeError:
        try:
            # Try latin-1 as fallback
            text = content.decode('latin-1')
            if len(text) > max_length:
                return text[:max_length] + "..."
            return text
        except UnicodeDecodeError:
            return None 