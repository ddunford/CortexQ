#!/usr/bin/env python3
"""
Manual data migration script to update domain references from names to UUIDs
Run this after the schema migration to fix existing data
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the src directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    return os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")

def migrate_domain_data():
    """Migrate existing data from domain names to domain IDs"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🔄 Starting domain data migration...")
        
        # Check if domain_id columns exist and domain columns exist
        tables_to_check = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages', 'connectors'
        ]
        
        for table in tables_to_check:
            logger.info(f"📋 Checking table: {table}")
            
            # Check if both domain and domain_id columns exist
            result = session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                AND column_name IN ('domain', 'domain_id')
                ORDER BY column_name
            """)).fetchall()
            
            columns = [row[0] for row in result]
            logger.info(f"   Columns found: {columns}")
            
            if 'domain' in columns and 'domain_id' in columns:
                logger.info(f"   ⚠️  Both domain and domain_id exist - need to migrate data")
                
                # Migrate data from domain name to domain_id
                logger.info(f"   🔄 Migrating {table} data...")
                
                # Update records where domain_id is NULL but domain has a value
                update_query = f"""
                    UPDATE {table} 
                    SET domain_id = od.id 
                    FROM organization_domains od 
                    WHERE {table}.organization_id = od.organization_id 
                    AND {table}.domain = od.domain_name
                    AND {table}.domain_id IS NULL
                """
                
                result = session.execute(text(update_query))
                logger.info(f"   ✅ Updated {result.rowcount} records in {table}")
                
                # Handle records with no matching domain (set to general domain)
                fallback_query = f"""
                    UPDATE {table} 
                    SET domain_id = (
                        SELECT od.id 
                        FROM organization_domains od 
                        WHERE od.organization_id = {table}.organization_id 
                        AND od.domain_name = 'general' 
                        LIMIT 1
                    )
                    WHERE domain_id IS NULL
                """
                
                result = session.execute(text(fallback_query))
                if result.rowcount > 0:
                    logger.info(f"   ✅ Set {result.rowcount} records to general domain in {table}")
                
            elif 'domain_id' in columns and 'domain' not in columns:
                logger.info(f"   ✅ {table} already migrated (only domain_id exists)")
                
            elif 'domain' in columns and 'domain_id' not in columns:
                logger.info(f"   ❌ {table} needs schema migration (only domain exists)")
                
            else:
                logger.info(f"   ⚠️  {table} has no domain columns")
        
        # Commit all changes
        session.commit()
        logger.info("✅ Domain data migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def verify_migration():
    """Verify that the migration was successful"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🔍 Verifying migration...")
        
        # Check for any NULL domain_id values
        tables_with_domain_id = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages', 'connectors'
        ]
        
        for table in tables_with_domain_id:
            # Check if domain_id column exists
            result = session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                AND column_name = 'domain_id'
            """)).fetchone()
            
            if result:
                # Count NULL domain_id values
                null_count = session.execute(text(f"""
                    SELECT COUNT(*) FROM {table} WHERE domain_id IS NULL
                """)).scalar()
                
                if null_count > 0:
                    logger.warning(f"⚠️  {table} has {null_count} records with NULL domain_id")
                else:
                    logger.info(f"✅ {table} - all records have domain_id")
        
        logger.info("✅ Migration verification completed!")
        
    except Exception as e:
        logger.error(f"❌ Verification failed: {e}")
        raise
    finally:
        session.close()

if __name__ == "__main__":
    try:
        migrate_domain_data()
        verify_migration()
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1) 