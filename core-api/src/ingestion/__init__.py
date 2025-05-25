"""
Ingestion modules for file processing and parsing
Migrated from services/ingestion/file-service/src/
"""

# FileProcessor is in background_processor.py, not utils.py
# from .utils import FileProcessor, FileValidator
from .crawler import WebCrawler, CrawlScheduler, crawler_scheduler

__all__ = [
    'WebCrawler',
    'CrawlScheduler',
    'crawler_scheduler'
] 