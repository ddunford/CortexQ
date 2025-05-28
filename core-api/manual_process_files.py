#!/usr/bin/env python3
"""
Manual File Processing Script
Processes files that were uploaded but failed to process due to storage issues
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, '/app/src')

from sqlalchemy import text
from sqlalchemy.orm import Session
from src.database import SessionLocal
from src.background_processor import FileProcessor

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def process_unprocessed_files():
    """Process all unprocessed files"""
    db = SessionLocal()
    processor = FileProcessor()
    await processor.initialize()
    
    try:
        # Get all unprocessed files
        unprocessed_files = db.execute(
            text("""
                SELECT f.id, f.original_filename, f.storage_type, f.object_key, f.file_path,
                       o.slug as org_slug, od.domain_name as domain
                FROM files f
                JOIN organizations o ON f.organization_id = o.id
                JOIN organization_domains od ON f.domain_id = od.id
                WHERE f.processed = false
                ORDER BY f.created_at ASC
            """)
        ).fetchall()
        
        logger.info(f"Found {len(unprocessed_files)} unprocessed files")
        
        for file_record in unprocessed_files:
            file_id = str(file_record.id)
            filename = file_record.original_filename
            
            logger.info(f"Processing {filename} (ID: {file_id})")
            
            try:
                success = await processor.process_file(file_id, db)
                if success:
                    logger.info(f"✅ Successfully processed {filename}")
                else:
                    logger.error(f"❌ Failed to process {filename}")
            except Exception as e:
                logger.error(f"❌ Error processing {filename}: {e}")
        
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(process_unprocessed_files()) 