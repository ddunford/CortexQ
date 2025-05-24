"""
Database models and connection for the Vector Index Service
"""

import uuid
from datetime import datetime
from typing import Generator

from sqlalchemy import create_engine, Column, String, Integer, Boolean, DateTime, Text, BigInteger
from sqlalchemy.dialects.postgresql import UUID, JSONB, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pgvector.sqlalchemy import Vector

from config import get_settings

settings = get_settings()

# Database setup
engine = create_engine(settings.DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class EmbeddingRecord(Base):
    """Embedding record model with domain support"""
    __tablename__ = "embeddings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(UUID(as_uuid=True))
    source_type = Column(String(50), default='file')
    domain = Column(String(50), default='general')  # Added domain support
    chunk_index = Column(Integer, default=0)
    content_text = Column(Text, nullable=False)
    content_hash = Column(String(64))
    embedding = Column(Vector(768))  # Updated to 768 dimensions for Ollama
    embedding_metadata = Column(JSONB, default={})  # Renamed from metadata to avoid SQLAlchemy conflict
    created_at = Column(DateTime, default=datetime.utcnow)


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """Create database tables"""
    Base.metadata.create_all(bind=engine) 