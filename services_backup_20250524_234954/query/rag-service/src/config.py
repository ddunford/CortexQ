"""
Configuration for RAG Service
"""

import os
from typing import List, Dict, Any
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """RAG Service Configuration"""
    
    # Service Configuration
    SERVICE_NAME: str = "rag-service"
    SERVICE_VERSION: str = "1.0.0"
    PORT: int = 8006
    DEBUG: bool = True
    LOG_LEVEL: str = "info"
    
    # Database Configuration
    DATABASE_URL: str = "postgresql://admin:password@localhost:5432/rag_searcher"
    
    # Redis Configuration
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_TTL_SECONDS: int = 3600  # 1 hour cache TTL
    
    # External Service URLs
    VECTOR_SERVICE_URL: str = "http://localhost:8002"
    CLASSIFICATION_SERVICE_URL: str = "http://localhost:8004"
    AGENT_SERVICE_URL: str = "http://localhost:8005"
    
    # CORS Configuration
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:8080,http://localhost:3001"
    
    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
    
    # RAG Processing Configuration
    MAX_SEARCH_RESULTS: int = 15
    MIN_CONFIDENCE_THRESHOLD: float = 0.3
    RESPONSE_CONFIDENCE_THRESHOLD: float = 0.7
    MAX_CONTEXT_LENGTH: int = 4000
    MAX_RESPONSE_LENGTH: int = 2000
    
    # Search Strategy Settings
    ENABLE_CROSS_DOMAIN_SEARCH: bool = True
    ENABLE_HYBRID_SEARCH: bool = True
    ENABLE_AGENT_INTEGRATION: bool = True
    
    # LLM Configuration for Response Generation
    LLM_PROVIDER: str = "ollama"  # ollama or openai
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama2:7b"
    OPENAI_API_KEY: str = "your_openai_key_here"
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.3
    
    # Response Templates by Domain
    DOMAIN_RESPONSE_STYLES: Dict[str, Dict[str, str]] = {
        "support": {
            "greeting": "I'll help you troubleshoot this issue.",
            "closing": "If this doesn't resolve your issue, please let me know and I can help you escalate to our support team.",
            "no_results": "I couldn't find specific information about this issue in our knowledge base. Let me connect you with our support team."
        },
        "sales": {
            "greeting": "I'd be happy to help you with information about our products and services.",
            "closing": "Would you like to speak with a sales representative for more detailed information?",
            "no_results": "I don't have specific information about this product inquiry. Let me connect you with our sales team."
        },
        "engineering": {
            "greeting": "Let me help you with this technical question.",
            "closing": "For more detailed technical assistance, our engineering team is available for consultation.",
            "no_results": "I couldn't find technical documentation for this question. Our engineering team can provide more specific guidance."
        },
        "product": {
            "greeting": "I can help you understand our product features and capabilities.",
            "closing": "For product roadmap questions, please check with our product management team.",
            "no_results": "I don't have current information about this product feature. Our product team can provide the latest updates."
        },
        "general": {
            "greeting": "I'm here to help with your question.",
            "closing": "Feel free to ask if you need more information or clarification.",
            "no_results": "I couldn't find specific information about your question. Please try rephrasing or contact our support team."
        }
    }
    
    # Response Generation Templates
    SINGLE_RESULT_TEMPLATE: str = """Based on the information I found:

{content}

**Source**: {source_title}
**Relevance**: {confidence}%"""

    MULTIPLE_RESULTS_TEMPLATE: str = """Based on the information I found:

{results}

**Sources**: {source_count} documents found
**Overall Confidence**: {confidence}%"""

    NO_RESULTS_TEMPLATE: str = """{domain_message}

**Suggestions**:
{suggestions}

**Next Steps**:
{next_steps}"""

    # Cache Configuration
    CACHE_RAG_RESPONSES: bool = True
    CACHE_SEARCH_RESULTS: bool = True
    RAG_CACHE_TTL: int = 1800  # 30 minutes
    SEARCH_CACHE_TTL: int = 900  # 15 minutes
    
    # Quality Thresholds
    MIN_RESULT_LENGTH: int = 50
    MAX_SOURCES_TO_DISPLAY: int = 5
    CONFIDENCE_BOOST_THRESHOLD: float = 0.8  # Boost confidence for very relevant results
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def get_settings() -> Settings:
    """Get application settings"""
    return Settings()


# Global settings instance
settings = get_settings() 