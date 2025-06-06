"""
Routes package for CortexQ API
Exports all routers for easy importing
"""

from .auth_routes import router as auth_router, user_router as auth_user_router, role_router as auth_role_router
from .file_routes import router as file_router, web_router as web_scraping_router, sources_router
from .organization_routes import router as organization_router, templates_router as domain_templates_router
from .analytics_routes import router as analytics_router
from .chat_routes import router as chat_router
from .search_routes import router as search_router
from .user_routes import router as user_router
from .debug_routes import router as debug_router
from .connectors import router as connectors_router

__all__ = [
    "auth_router",
    "auth_user_router",
    "auth_role_router",
    "file_router", 
    "web_scraping_router",
    "sources_router",
    "organization_router",
    "domain_templates_router",
    "analytics_router",
    "chat_router",
    "search_router",
    "user_router",
    "debug_router",
    "connectors_router"
] 