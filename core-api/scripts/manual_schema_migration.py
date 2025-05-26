#!/usr/bin/env python3
"""
Manual schema migration script to add domain_id columns and migrate data
This handles the schema changes that the Alembic migration failed to apply
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment"""
    return os.getenv("DATABASE_URL", "postgresql://admin:password@postgres:5432/rag_searcher")

def apply_schema_changes():
    """Apply the schema changes manually"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🔄 Starting manual schema migration...")
        
        # Define tables that need domain_id columns
        tables_to_migrate = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages'
        ]
        
        for table in tables_to_migrate:
            logger.info(f"📋 Processing table: {table}")
            
            # Check if domain_id column already exists
            result = session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                AND column_name = 'domain_id'
            """)).fetchone()
            
            if not result:
                logger.info(f"   ➕ Adding domain_id column to {table}")
                
                # Add domain_id column
                session.execute(text(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN domain_id UUID
                """))
                
                # Add foreign key constraint
                session.execute(text(f"""
                    ALTER TABLE {table} 
                    ADD CONSTRAINT fk_{table}_domain_id 
                    FOREIGN KEY (domain_id) 
                    REFERENCES organization_domains(id) 
                    ON DELETE CASCADE
                """))
                
                logger.info(f"   ✅ Added domain_id column and foreign key to {table}")
            else:
                logger.info(f"   ✅ {table} already has domain_id column")
        
        # Commit schema changes
        session.commit()
        logger.info("✅ Schema changes applied successfully!")
        
    except Exception as e:
        logger.error(f"❌ Schema migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def migrate_data():
    """Migrate data from domain names to domain IDs"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🔄 Starting data migration...")
        
        tables_to_migrate = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages', 'connectors'
        ]
        
        for table in tables_to_migrate:
            logger.info(f"📋 Migrating data in: {table}")
            
            # Update records to use domain_id based on domain name
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
        
        # Commit data changes
        session.commit()
        logger.info("✅ Data migration completed successfully!")
        
    except Exception as e:
        logger.error(f"❌ Data migration failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def make_domain_id_not_null():
    """Make domain_id columns NOT NULL after data migration"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🔒 Making domain_id columns NOT NULL...")
        
        tables_to_update = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages', 'connectors'
        ]
        
        for table in tables_to_update:
            logger.info(f"📋 Updating {table} domain_id to NOT NULL")
            
            # Check for any NULL values first
            null_count = session.execute(text(f"""
                SELECT COUNT(*) FROM {table} WHERE domain_id IS NULL
            """)).scalar()
            
            if null_count > 0:
                logger.warning(f"   ⚠️  {table} has {null_count} NULL domain_id values - skipping NOT NULL constraint")
                continue
            
            # Make domain_id NOT NULL
            session.execute(text(f"""
                ALTER TABLE {table} 
                ALTER COLUMN domain_id SET NOT NULL
            """))
            
            logger.info(f"   ✅ {table}.domain_id is now NOT NULL")
        
        # Commit changes
        session.commit()
        logger.info("✅ NOT NULL constraints applied successfully!")
        
    except Exception as e:
        logger.error(f"❌ NOT NULL constraint application failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def create_indexes():
    """Create indexes for domain_id columns"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("📈 Creating indexes for domain_id columns...")
        
        # Define indexes to create
        indexes = [
            ("files", "idx_files_domain_id", "domain_id"),
            ("files", "idx_files_org_domain_new", "organization_id, domain_id"),
            ("file_processing_jobs", "idx_file_processing_jobs_domain_id", "domain_id"),
            ("file_processing_jobs", "idx_file_processing_jobs_org_domain_new", "organization_id, domain_id"),
            ("embeddings", "idx_embeddings_domain_id", "domain_id"),
            ("embeddings", "idx_embeddings_org_domain_new", "organization_id, domain_id"),
            ("chat_sessions", "idx_chat_sessions_domain_id", "domain_id"),
            ("chat_sessions", "idx_chat_sessions_org_domain_new", "organization_id, domain_id"),
            ("classification_results", "idx_classification_results_domain_id", "domain_id"),
            ("classification_results", "idx_classification_results_org_domain_new", "organization_id, domain_id"),
            ("rag_executions", "idx_rag_executions_domain_id", "domain_id"),
            ("rag_executions", "idx_rag_executions_org_domain_new", "organization_id, domain_id"),
            ("crawled_pages", "idx_crawled_pages_domain_id", "domain_id"),
            ("crawled_pages", "idx_crawled_pages_org_domain_new", "organization_id, domain_id"),
        ]
        
        for table, index_name, columns in indexes:
            try:
                session.execute(text(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({columns})
                """))
                logger.info(f"   ✅ Created index {index_name} on {table}")
            except Exception as e:
                logger.warning(f"   ⚠️  Failed to create index {index_name}: {e}")
        
        # Commit changes
        session.commit()
        logger.info("✅ Indexes created successfully!")
        
    except Exception as e:
        logger.error(f"❌ Index creation failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

def drop_old_domain_columns():
    """Drop the old domain string columns after migration"""
    
    database_url = get_database_url()
    engine = create_engine(database_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        logger.info("🗑️ Dropping old domain string columns...")
        
        tables_to_update = [
            'files', 'file_processing_jobs', 'embeddings', 'chat_sessions',
            'classification_results', 'rag_executions', 'crawled_pages', 'connectors'
        ]
        
        for table in tables_to_update:
            # Check if domain column exists
            result = session.execute(text(f"""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                AND column_name = 'domain'
            """)).fetchone()
            
            if result:
                logger.info(f"   🗑️ Dropping domain column from {table}")
                session.execute(text(f"ALTER TABLE {table} DROP COLUMN domain"))
                logger.info(f"   ✅ Dropped domain column from {table}")
            else:
                logger.info(f"   ✅ {table} domain column already dropped")
        
        # Commit changes
        session.commit()
        logger.info("✅ Old domain columns dropped successfully!")
        
    except Exception as e:
        logger.error(f"❌ Column dropping failed: {e}")
        session.rollback()
        raise
    finally:
        session.close()

if __name__ == "__main__":
    try:
        apply_schema_changes()
        migrate_data()
        make_domain_id_not_null()
        create_indexes()
        
        # Ask user before dropping old columns
        print("\n" + "="*60)
        print("⚠️  READY TO DROP OLD DOMAIN COLUMNS")
        print("This will permanently remove the 'domain' string columns.")
        print("Make sure everything is working correctly first!")
        print("="*60)
        
        response = input("Drop old domain columns? (y/N): ").strip().lower()
        if response == 'y':
            drop_old_domain_columns()
        else:
            logger.info("Skipping old column removal. You can run this later.")
        
        logger.info("🎉 Manual schema migration completed successfully!")
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        sys.exit(1) 