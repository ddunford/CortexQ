"""
Configuration for Audit Service
"""

import os
from typing import List


class Settings:
    """Application settings"""
    
    # Service info
    SERVICE_NAME: str = "audit-service"
    SERVICE_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "info").upper()
    PORT: int = int(os.getenv("PORT", "8008"))
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql://admin:password@localhost:5432/rag_searcher"
    )
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # CORS
    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get CORS origins as list"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-here")
    JWT_ALGORITHM: str = "HS256"
    
    # Audit settings
    AUDIT_RETENTION_DAYS: int = int(os.getenv("AUDIT_RETENTION_DAYS", "365"))
    SECURITY_ALERT_THRESHOLD: int = int(os.getenv("SECURITY_ALERT_THRESHOLD", "5"))
    
    # Compliance settings
    GDPR_ENABLED: bool = os.getenv("GDPR_ENABLED", "true").lower() == "true"
    CCPA_ENABLED: bool = os.getenv("CCPA_ENABLED", "true").lower() == "true"
    SOX_ENABLED: bool = os.getenv("SOX_ENABLED", "false").lower() == "true"


settings = Settings() 