"""
Database dependency functions
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/cortexq")

# Database setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 