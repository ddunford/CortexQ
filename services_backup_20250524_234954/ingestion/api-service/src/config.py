"""
Configuration for API Integration Service
"""

import os
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """API Integration Service Configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "api-integration-service"
    SERVICE_VERSION: str = "1.0.0"
    PORT: int = 8008
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TTL_SECONDS: int = 3600  # 1 hour cache TTL
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:3001"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # External Service URLs
    FILE_SERVICE_URL: str = "http://localhost:8001"
    VECTOR_SERVICE_URL: str = "http://localhost:8002"
    
    # API Connector Settings
    MAX_SYNC_WORKERS: int = 5
    SYNC_TIMEOUT_SECONDS: int = 3600  # 1 hour
    RETRY_ATTEMPTS: int = 3
    RETRY_DELAY_SECONDS: int = 60
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


# Global settings instance
settings = get_settings() 