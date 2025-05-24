"""
Database configuration and session management for RAG Service
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
        logger.info("Creating RAG service database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("RAG service database tables created successfully")
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
    """Initialize database"""
    try:
        create_tables()
        logger.info("RAG service database initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise


def check_database_health() -> bool:
    """Check if database is accessible"""
    try:
        with SessionLocal() as db:
            db.execute("SELECT 1")
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False 