"""
Configuration management for the Intent Classification Service
"""

import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings for Intent Classification Service"""
    
    # Database
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis for caching
    REDIS_URL: str = "redis://localhost:6379"
    
    # External Services
    VECTOR_SERVICE_URL: str = "http://localhost:8002"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # OpenAI Configuration (fallback)
    OPENAI_API_KEY: str = "your_openai_key_here"
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    
    # Classification Configuration
    CLASSIFICATION_SERVICE_PORT: int = 8004
    MAX_QUERY_LENGTH: int = 2000
    MAX_BATCH_SIZE: int = 50
    MIN_CONFIDENCE_THRESHOLD: float = 0.6
    HIGH_CONFIDENCE_THRESHOLD: float = 0.8
    
    # LLM Provider Settings
    LLM_PROVIDER: str = "ollama"  # ollama or openai
    LLM_MODEL: str = "llama3.2:3b"  # Default Ollama model for classification
    LLM_TIMEOUT: int = 30
    LLM_MAX_RETRIES: int = 3
    
    # Intent Categories
    INTENT_CATEGORIES: List[str] = [
        "bug_report",
        "feature_request", 
        "training",
        "general"
    ]
    
    # Classification Features
    ENABLE_CONTEXT_ANALYSIS: bool = True
    ENABLE_PATTERN_MATCHING: bool = True
    ENABLE_KEYWORD_ANALYSIS: bool = True
    ENABLE_LLM_CLASSIFICATION: bool = True
    ENABLE_CONFIDENCE_BOOSTING: bool = True
    
    # Cache Settings
    CACHE_CLASSIFICATION_RESULTS: bool = True
    CACHE_EXPIRATION_MINUTES: int = 60
    CACHE_MAX_SIZE: int = 1000
    
    # Analytics and Monitoring
    ENABLE_ANALYTICS: bool = True
    ANALYTICS_RETENTION_DAYS: int = 90
    ENABLE_PERFORMANCE_METRICS: bool = True
    
    # Feedback and Learning
    ENABLE_FEEDBACK_LEARNING: bool = True
    MIN_FEEDBACK_FOR_RETRAINING: int = 10
    AUTO_RETRAIN_THRESHOLD: float = 0.7  # Retrain if accuracy drops below this
    
    # Development
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:8090"
    
    # Intent-specific Configuration
    BUG_REPORT_KEYWORDS: List[str] = [
        "error", "bug", "crash", "issue", "problem", "broken", "fail", "exception", 
        "not working", "doesn't work", "stopped working", "freezing", "hanging",
        "timeout", "500", "404", "403", "401", "stack trace", "traceback"
    ]
    
    FEATURE_REQUEST_KEYWORDS: List[str] = [
        "feature", "enhancement", "improvement", "suggestion", "request", "add",
        "implement", "support", "ability", "option", "setting", "configuration",
        "can we", "could we", "would be nice", "wish", "want", "need"
    ]
    
    TRAINING_KEYWORDS: List[str] = [
        "how", "tutorial", "guide", "documentation", "learn", "training", "help",
        "explain", "show", "teach", "understand", "configure", "setup", "install",
        "integrate", "example", "sample", "best practice", "workflow"
    ]
    
    # Pattern Recognition
    BUG_PATTERNS: List[str] = [
        r"getting.*error",
        r"fails.*to.*work",
        r"not.*working.*properly",
        r"throws.*exception",
        r"returns.*\d{3}.*error",
        r"crashes.*when",
        r"stopped.*working.*after"
    ]
    
    FEATURE_PATTERNS: List[str] = [
        r"can.*we.*add",
        r"would.*like.*to.*see",
        r"feature.*request",
        r"enhancement.*for",
        r"ability.*to.*do",
        r"option.*to.*configure",
        r"support.*for.*\w+"
    ]
    
    TRAINING_PATTERNS: List[str] = [
        r"how.*do.*i",
        r"how.*to.*\w+",
        r"what.*is.*the.*way",
        r"best.*practice.*for",
        r"tutorial.*on.*\w+",
        r"guide.*for.*\w+",
        r"how.*can.*i.*configure"
    ]
    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Get list of CORS origins"""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings() 