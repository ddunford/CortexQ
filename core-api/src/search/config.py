"""
Configuration management for the Vector Index Service
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
    
    # LLM Configuration
    OPENAI_API_KEY: str = "your_openai_key_here"
    OLLAMA_BASE_URL: str = "https://ollama.glitched.dev"
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    EMBEDDING_PROVIDER: str = "ollama"  # openai or ollama
    
    # Vector Configuration
    VECTOR_DIMENSION: int = 768  # Ollama nomic-embed-text dimension
    SIMILARITY_THRESHOLD: float = 0.7
    MAX_SEARCH_RESULTS: int = 10
    
    # Vector Store Configuration
    VECTOR_STORE_TYPE: str = "faiss"  # faiss, pgvector, or opensearch
    FAISS_INDEX_PATH: str = "./vector_index"
    
    # Service Configuration
    VECTOR_SERVICE_PORT: int = 8002
    
    # Development
    DEBUG: bool = True
    LOG_LEVEL: str = "debug"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080"
    
    # Performance
    BATCH_SIZE: int = 32
    MAX_CONCURRENT_REQUESTS: int = 10
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 