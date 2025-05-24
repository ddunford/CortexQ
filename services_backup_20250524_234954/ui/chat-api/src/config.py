"""
Configuration management for the Chat API Service
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings"""
    
    # Database
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis for session caching
    REDIS_URL: str = "redis://localhost:6379"
    
    # External Services
    VECTOR_SERVICE_URL: str = "http://localhost:8002"
    FILE_SERVICE_URL: str = "http://localhost:8001"
    
    # Chat Configuration
    MAX_SESSION_DURATION_HOURS: int = 24
    MAX_MESSAGE_LENGTH: int = 2000
    MAX_CONTEXT_MESSAGES: int = 10
    DEFAULT_RESPONSE_TIMEOUT: int = 30
    
    # WebSocket Configuration
    WEBSOCKET_TIMEOUT: int = 300  # 5 minutes
    MAX_CONNECTIONS_PER_USER: int = 5
    
    # Service Configuration
    CHAT_API_PORT: int = 8003
    
    # Development
    DEBUG: bool = True
    LOG_LEVEL: str = "debug"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:3001"
    
    # Response Generation
    ENABLE_STREAMING: bool = True
    ENABLE_SUGGESTIONS: bool = True
    MIN_CONFIDENCE_THRESHOLD: float = 0.3
    
    # Domain-specific settings
    DEFAULT_DOMAIN: str = "general"
    ENABLE_DOMAIN_AUTO_DETECTION: bool = True
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 