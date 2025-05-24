"""
Configuration for Agent Workflow Service
"""

import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Agent Workflow Service Configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "agent-workflow-service"
    SERVICE_VERSION: str = "1.0.0"
    PORT: int = 8005
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TTL_SECONDS: int = 3600  # 1 hour cache TTL
    
    # External Service URLs
    CLASSIFICATION_SERVICE_URL: str = "http://localhost:8004"
    VECTOR_SERVICE_URL: str = "http://localhost:8002"
    FILE_SERVICE_URL: str = "http://localhost:8001"
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:3001"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # Workflow Configuration
    CONFIDENCE_THRESHOLD: float = 0.7
    MAX_SEARCH_RESULTS: int = 10
    MAX_CONTEXT_LENGTH: int = 4000
    
    # Bug Detection Workflow Settings
    BUG_WORKFLOW_ENABLED: bool = True
    BUG_KNOWN_ISSUES_THRESHOLD: float = 0.8
    BUG_ERROR_PATTERNS: List[str] = [
        r"error|exception|fail|crash|bug|issue",
        r"not working|broken|doesn't work",
        r"stack trace|traceback|null pointer",
        r"timeout|connection refused|404|500"
    ]
    
    # Feature Request Workflow Settings
    FEATURE_WORKFLOW_ENABLED: bool = True
    FEATURE_BACKLOG_THRESHOLD: float = 0.75
    FEATURE_REQUEST_KEYWORDS: List[str] = [
        "request", "feature", "enhancement", "add", "implement", 
        "support", "integrate", "improve", "upgrade", "extend"
    ]
    
    # Training/Documentation Workflow Settings
    TRAINING_WORKFLOW_ENABLED: bool = True
    TRAINING_DOC_THRESHOLD: float = 0.7
    TRAINING_KEYWORDS: List[str] = [
        "how", "guide", "tutorial", "documentation", "help",
        "learn", "setup", "configure", "install", "deploy"
    ]
    
    # External API Integration Settings
    JIRA_ENABLED: bool = False
    JIRA_BASE_URL: str = ""
    JIRA_USERNAME: str = ""
    JIRA_API_TOKEN: str = ""
    
    GITHUB_ENABLED: bool = False
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = ""
    
    CONFLUENCE_ENABLED: bool = False
    CONFLUENCE_BASE_URL: str = ""
    CONFLUENCE_USERNAME: str = ""
    CONFLUENCE_API_TOKEN: str = ""
    
    # LLM Configuration for Response Generation
    LLM_PROVIDER: str = "ollama"  # ollama or openai
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2:7b"
    OPENAI_API_KEY: str = "your_openai_key_here"
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.3
    
    # Workflow Response Templates
    BUG_RESPONSE_TEMPLATE: str = """
## 🐛 Bug Report Analysis

**Issue Summary**: {summary}

**Likely Cause**: {probable_cause}

**Known Solutions**:
{known_solutions}

**Recommended Actions**:
{recommended_actions}

**Developer Notes**:
{dev_notes}

**Related Issues**: {related_issues}
"""

    FEATURE_RESPONSE_TEMPLATE: str = """
## 💡 Feature Request Analysis

**Request Summary**: {summary}

**Current Status**: {status}

**Existing Similar Features**:
{existing_features}

**Proposed Implementation**:
{implementation_notes}

**Business Impact**: {business_impact}

**Next Steps**: {next_steps}
"""

    TRAINING_RESPONSE_TEMPLATE: str = """
## 📚 Training & Documentation

**Topic**: {topic}

**Step-by-Step Guide**:
{step_by_step}

**Code Examples**:
{code_examples}

**Additional Resources**:
{resources}

**Related Documentation**: {related_docs}
"""

    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


# Global settings instance
settings = get_settings() 