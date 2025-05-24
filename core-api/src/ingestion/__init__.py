"""
Ingestion modules for file processing and parsing
Migrated from services/ingestion/file-service/src/
"""

from .utils import FileProcessor, FileValidator
from .crawler import WebCrawler, CrawlScheduler, crawler_scheduler

__all__ = [
    'FileProcessor',
    'FileValidator',
    'WebCrawler',
    'CrawlScheduler',
    'crawler_scheduler'
] 