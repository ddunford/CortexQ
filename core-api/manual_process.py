#!/usr/bin/env python3
"""
Manual file processing trigger
"""

import asyncio
import sys
import os
sys.path.append('/app/src')

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from background_processor import FileProcessor

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

async def main():
    """Manually trigger file processing"""
    print("🔧 Manual File Processing Trigger")
    
    # Initialize file processor
    processor = FileProcessor()
    await processor.initialize()
    
    # Check if embeddings service is available
    if processor.embeddings_service and processor.embeddings_service.is_available():
        print("✅ Embeddings service available - will generate real embeddings")
    else:
        print("⚠️ Embeddings service not available - will use mock embeddings")
    
    db = SessionLocal()
    try:
        # Get unprocessed files
        result = db.execute(
            text("""
                SELECT f.id, f.original_filename, f.processed, f.processing_status
                FROM files f
                WHERE f.processed = false OR f.processing_status IN ('pending', 'failed') OR f.processed IS NULL
                ORDER BY f.created_at DESC
                LIMIT 10
            """)
        )
        
        files = result.fetchall()
        print(f"Found {len(files)} files to process:")
        
        for file_row in files:
            print(f"  - {file_row.original_filename} (ID: {file_row.id}, Status: {file_row.processing_status})")
            
            # Process the file
            print(f"Processing {file_row.original_filename}...")
            success = await processor.process_file(str(file_row.id), db)
            
            if success:
                print(f"✅ Successfully processed {file_row.original_filename}")
            else:
                print(f"❌ Failed to process {file_row.original_filename}")
            
            print("-" * 50)
    
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main()) 