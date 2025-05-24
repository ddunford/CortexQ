"""
Configuration for Authentication Service
"""

import os
from typing import List, Dict, ClassVar
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Authentication Service Configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "auth-service"
    SERVICE_VERSION: str = "1.0.0"
    PORT: int = 8007
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TTL_SECONDS: int = 3600  # 1 hour cache TTL
    
    # JWT Configuration
    JWT_SECRET_KEY: str = "your-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Password Configuration
    PASSWORD_MIN_LENGTH: int = 8
    PASSWORD_REQUIRE_UPPERCASE: bool = True
    PASSWORD_REQUIRE_LOWERCASE: bool = True
    PASSWORD_REQUIRE_NUMBERS: bool = True
    PASSWORD_REQUIRE_SPECIAL: bool = False
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:3001"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Default Admin User
    DEFAULT_ADMIN_EMAIL: str = "admin@example.com"
    DEFAULT_ADMIN_PASSWORD: str = "admin123"
    
    # Domain Access Control
    DOMAIN_PERMISSIONS: ClassVar[Dict[str, List[str]]] = {
        "admin": ["general", "support", "sales", "engineering", "product"],
        "support": ["general", "support"],
        "sales": ["general", "sales"],
        "engineering": ["general", "engineering"],
        "product": ["general", "product"],
        "user": ["general"]
    }
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


# Global settings instance
settings = get_settings() 