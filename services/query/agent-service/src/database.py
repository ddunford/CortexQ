"""
Database configuration and session management for Agent Workflow Service
"""

import logging
from typing import Generator

from sqlalchemy import create_engine, MetaData
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from config import settings
from models import Base

logger = logging.getLogger(__name__)

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,
    echo=settings.DEBUG
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create metadata
metadata = MetaData()


def create_tables():
    """Create database tables"""
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except SQLAlchemyError as e:
        logger.error(f"Error creating database tables: {e}")
        raise


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    except SQLAlchemyError as e:
        logger.error(f"Database error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def init_database():
    """Initialize database with sample data"""
    try:
        create_tables()
        
        # Create sample known issues
        db = SessionLocal()
        try:
            from models import KnownIssue, Priority
            
            # Check if we already have sample data
            existing_issues = db.query(KnownIssue).count()
            if existing_issues == 0:
                logger.info("Creating sample known issues...")
                
                sample_issues = [
                    KnownIssue(
                        title="File Upload Size Limit Exceeded",
                        description="Users encounter errors when uploading files larger than 50MB",
                        solution="Configure chunked upload or increase server memory allocation. Update nginx client_max_body_size setting.",
                        error_patterns=["file.*too.*large", "413.*payload.*too.*large", "request.*entity.*too.*large"],
                        keywords=["upload", "file", "size", "limit", "large", "413"],
                        priority=Priority.HIGH,
                        occurrence_count=15,
                        resolution_time_avg=30.0,
                        documentation_url="https://docs.example.com/file-upload-limits"
                    ),
                    KnownIssue(
                        title="Database Connection Timeout",
                        description="Intermittent database connection timeouts during peak hours",
                        solution="Increase connection pool size and adjust timeout settings. Consider implementing connection retry logic.",
                        error_patterns=["connection.*timeout", "database.*unavailable", "pool.*exhausted"],
                        keywords=["database", "connection", "timeout", "pool", "unavailable"],
                        priority=Priority.CRITICAL,
                        occurrence_count=8,
                        resolution_time_avg=45.0,
                        documentation_url="https://docs.example.com/database-troubleshooting"
                    ),
                    KnownIssue(
                        title="API Rate Limit Exceeded",
                        description="External API calls fail due to rate limiting",
                        solution="Implement exponential backoff retry logic and consider API key rotation or premium tier upgrade.",
                        error_patterns=["rate.*limit.*exceeded", "429.*too.*many.*requests", "quota.*exceeded"],
                        keywords=["api", "rate", "limit", "quota", "429", "too many requests"],
                        priority=Priority.MEDIUM,
                        occurrence_count=22,
                        resolution_time_avg=15.0,
                        documentation_url="https://docs.example.com/api-rate-limits"
                    ),
                    KnownIssue(
                        title="Session Timeout Issues",
                        description="Users being logged out unexpectedly",
                        solution="Check JWT token expiration settings and refresh token implementation. Verify session storage configuration.",
                        error_patterns=["session.*expired", "unauthorized.*access", "token.*invalid"],
                        keywords=["session", "timeout", "logout", "token", "expired", "unauthorized"],
                        priority=Priority.MEDIUM,
                        occurrence_count=35,
                        resolution_time_avg=20.0,
                        documentation_url="https://docs.example.com/session-management"
                    ),
                    KnownIssue(
                        title="Memory Leak in Vector Processing",
                        description="Memory consumption increases over time during vector operations",
                        solution="Update to latest FAISS version and implement proper cleanup in embedding pipeline. Monitor memory usage patterns.",
                        error_patterns=["memory.*leak", "out.*of.*memory", "oom.*killed"],
                        keywords=["memory", "leak", "vector", "faiss", "oom", "embedding"],
                        priority=Priority.HIGH,
                        occurrence_count=5,
                        resolution_time_avg=120.0,
                        documentation_url="https://docs.example.com/vector-optimization"
                    )
                ]
                
                for issue in sample_issues:
                    db.add(issue)
                
                db.commit()
                logger.info(f"Created {len(sample_issues)} sample known issues")
            
        except Exception as e:
            logger.error(f"Error creating sample data: {e}")
            db.rollback()
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


# Database health check
def check_database_health() -> bool:
    """Check if database is accessible"""
    try:
        with SessionLocal() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False 