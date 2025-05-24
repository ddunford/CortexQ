"""
Configuration management for the File Ingestion Service
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379"
    
    # File Storage
    FILE_STORAGE_PATH: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 100
    ALLOWED_FILE_TYPES: str = "pdf,docx,txt,md,json,csv,yaml,py,js,java,cpp,html,xml"
    
    # Service Configuration
    FILE_SERVICE_PORT: int = 8001
    
    # Development
    DEBUG: bool = True
    LOG_LEVEL: str = "debug"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def allowed_file_extensions(self) -> List[str]:
        """Get list of allowed file extensions"""
        return [ext.strip().lower() for ext in self.ALLOWED_FILE_TYPES.split(",")]
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 