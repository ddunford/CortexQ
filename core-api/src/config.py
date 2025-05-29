"""
Configuration settings for the CortexQ system
"""

import os
from typing import List


class Settings:
    """Application settings"""
    
    def __init__(self):
        self.allowed_file_extensions = [
            'pdf', 'docx', 'doc', 'txt', 'md', 'markdown',
            'json', 'csv', 'yaml', 'yml', 'py', 'js', 'ts',
            'java', 'cpp', 'c', 'h', 'html', 'xml'
        ]
        
        self.max_file_size = int(os.getenv('MAX_FILE_SIZE', 50 * 1024 * 1024))  # 50MB
        self.database_url = os.getenv('DATABASE_URL', 'postgresql://admin:password@localhost:5432/cortexq')
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.jwt_secret = os.getenv('JWT_SECRET', 'your-super-secret-jwt-key')
        self.debug = os.getenv('DEBUG', 'false').lower() == 'true'
        
        # LLM settings
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.openai_api_key = os.getenv('OPENAI_API_KEY', '')
        
        # Embedding settings
        self.EMBEDDING_PROVIDER = os.getenv('EMBEDDING_PROVIDER', 'ollama')  # 'openai' or 'ollama'
        self.EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'text-embedding-3-small')  # OpenAI model
        self.VECTOR_DIMENSION = int(os.getenv('VECTOR_DIMENSION', '768'))  # Updated for nomic-embed-text
        self.OLLAMA_BASE_URL = self.ollama_base_url  # Alias for consistency
        self.OPENAI_API_KEY = self.openai_api_key  # Alias for consistency
        
        # MinIO settings
        self.minio_endpoint = os.getenv('MINIO_ENDPOINT', 'localhost:9000')
        self.minio_access_key = os.getenv('MINIO_ACCESS_KEY', 'minioadmin')
        self.minio_secret_key = os.getenv('MINIO_SECRET_KEY', 'minioadmin123')
        self.minio_secure = os.getenv('MINIO_SECURE', 'false').lower() == 'true'


# Global settings instance
_settings = None


def get_settings() -> Settings:
    """Get application settings (singleton)"""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings 