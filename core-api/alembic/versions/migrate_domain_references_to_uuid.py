"""Migrate all domain references from names to UUIDs

Revision ID: migrate_domain_refs_to_uuid
Revises: add_connectors_sync_jobs
Create Date: 2024-12-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision: str = 'migrate_domain_refs_to_uuid'
down_revision: Union[str, None] = 'add_connectors_sync_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migrate all tables from using domain names to domain UUIDs
    """
    
    # Get connection for data migration
    connection = op.get_bind()
    
    print("🔄 Starting migration from domain names to domain UUIDs...")
    
    # ========================================================================
    # STEP 1: Add new domain_id columns to all affected tables
    # ========================================================================
    
    print("📝 Adding domain_id columns...")
    
    # Add domain_id to files table
    op.add_column('files', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_files_domain_id', 'files', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to file_processing_jobs table
    op.add_column('file_processing_jobs', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_file_processing_jobs_domain_id', 'file_processing_jobs', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to embeddings table
    op.add_column('embeddings', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_embeddings_domain_id', 'embeddings', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to chat_sessions table
    op.add_column('chat_sessions', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_chat_sessions_domain_id', 'chat_sessions', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to classification_results table
    op.add_column('classification_results', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_classification_results_domain_id', 'classification_results', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to rag_executions table
    op.add_column('rag_executions', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_rag_executions_domain_id', 'rag_executions', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Add domain_id to crawled_pages table
    op.add_column('crawled_pages', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_crawled_pages_domain_id', 'crawled_pages', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # Update connectors table to use domain_id instead of domain string
    op.add_column('connectors', sa.Column('domain_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key('fk_connectors_domain_id', 'connectors', 'organization_domains', ['domain_id'], ['id'], ondelete='CASCADE')
    
    # ========================================================================
    # STEP 2: Populate domain_id columns with corresponding UUID values
    # ========================================================================
    
    print("🔄 Populating domain_id columns with corresponding UUIDs...")
    
    # Files table migration
    connection.execute(text("""
        UPDATE files 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE files.organization_id = od.organization_id 
        AND files.domain = od.domain_name
    """))
    
    # Handle files with no matching domain (set to general domain)
    connection.execute(text("""
        UPDATE files 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = files.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # File processing jobs table migration
    connection.execute(text("""
        UPDATE file_processing_jobs 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE file_processing_jobs.organization_id = od.organization_id 
        AND file_processing_jobs.domain = od.domain_name
    """))
    
    # Handle file processing jobs with no matching domain
    connection.execute(text("""
        UPDATE file_processing_jobs 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = file_processing_jobs.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # Embeddings table migration
    connection.execute(text("""
        UPDATE embeddings 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE embeddings.organization_id = od.organization_id 
        AND embeddings.domain = od.domain_name
    """))
    
    # Handle embeddings with no matching domain
    connection.execute(text("""
        UPDATE embeddings 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = embeddings.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # Chat sessions table migration
    connection.execute(text("""
        UPDATE chat_sessions 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE chat_sessions.organization_id = od.organization_id 
        AND chat_sessions.domain = od.domain_name
    """))
    
    # Handle chat sessions with no matching domain
    connection.execute(text("""
        UPDATE chat_sessions 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = chat_sessions.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # Classification results table migration
    connection.execute(text("""
        UPDATE classification_results 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE classification_results.organization_id = od.organization_id 
        AND classification_results.domain = od.domain_name
    """))
    
    # Handle classification results with no matching domain
    connection.execute(text("""
        UPDATE classification_results 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = classification_results.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # RAG executions table migration
    connection.execute(text("""
        UPDATE rag_executions 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE rag_executions.organization_id = od.organization_id 
        AND rag_executions.domain = od.domain_name
    """))
    
    # Handle RAG executions with no matching domain
    connection.execute(text("""
        UPDATE rag_executions 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = rag_executions.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # Crawled pages table migration
    connection.execute(text("""
        UPDATE crawled_pages 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE crawled_pages.organization_id = od.organization_id 
        AND crawled_pages.domain = od.domain_name
    """))
    
    # Handle crawled pages with no matching domain
    connection.execute(text("""
        UPDATE crawled_pages 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = crawled_pages.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # Connectors table migration
    connection.execute(text("""
        UPDATE connectors 
        SET domain_id = od.id 
        FROM organization_domains od 
        WHERE connectors.organization_id = od.organization_id 
        AND connectors.domain = od.domain_name
    """))
    
    # Handle connectors with no matching domain
    connection.execute(text("""
        UPDATE connectors 
        SET domain_id = (
            SELECT od.id 
            FROM organization_domains od 
            WHERE od.organization_id = connectors.organization_id 
            AND od.domain_name = 'general' 
            LIMIT 1
        )
        WHERE domain_id IS NULL
    """))
    
    # ========================================================================
    # STEP 3: Make domain_id columns non-nullable
    # ========================================================================
    
    print("🔒 Making domain_id columns non-nullable...")
    
    op.alter_column('files', 'domain_id', nullable=False)
    op.alter_column('file_processing_jobs', 'domain_id', nullable=False)
    op.alter_column('embeddings', 'domain_id', nullable=False)
    op.alter_column('chat_sessions', 'domain_id', nullable=False)
    op.alter_column('classification_results', 'domain_id', nullable=False)
    op.alter_column('rag_executions', 'domain_id', nullable=False)
    op.alter_column('crawled_pages', 'domain_id', nullable=False)
    op.alter_column('connectors', 'domain_id', nullable=False)
    
    # ========================================================================
    # STEP 4: Create indexes for domain_id columns
    # ========================================================================
    
    print("📈 Creating indexes for domain_id columns...")
    
    op.create_index('idx_files_domain_id', 'files', ['domain_id'])
    op.create_index('idx_files_org_domain', 'files', ['organization_id', 'domain_id'])
    
    op.create_index('idx_file_processing_jobs_domain_id', 'file_processing_jobs', ['domain_id'])
    op.create_index('idx_file_processing_jobs_org_domain', 'file_processing_jobs', ['organization_id', 'domain_id'])
    
    op.create_index('idx_embeddings_domain_id', 'embeddings', ['domain_id'])
    op.create_index('idx_embeddings_org_domain', 'embeddings', ['organization_id', 'domain_id'])
    
    op.create_index('idx_chat_sessions_domain_id', 'chat_sessions', ['domain_id'])
    op.create_index('idx_chat_sessions_org_domain', 'chat_sessions', ['organization_id', 'domain_id'])
    
    op.create_index('idx_classification_results_domain_id', 'classification_results', ['domain_id'])
    op.create_index('idx_classification_results_org_domain', 'classification_results', ['organization_id', 'domain_id'])
    
    op.create_index('idx_rag_executions_domain_id', 'rag_executions', ['domain_id'])
    op.create_index('idx_rag_executions_org_domain', 'rag_executions', ['organization_id', 'domain_id'])
    
    op.create_index('idx_crawled_pages_domain_id', 'crawled_pages', ['domain_id'])
    op.create_index('idx_crawled_pages_org_domain', 'crawled_pages', ['organization_id', 'domain_id'])
    
    # Update connectors indexes
    op.drop_index('idx_connectors_domain', 'connectors')
    op.drop_index('idx_connectors_org_domain', 'connectors')
    op.create_index('idx_connectors_domain_id', 'connectors', ['domain_id'])
    op.create_index('idx_connectors_org_domain_id', 'connectors', ['organization_id', 'domain_id'])
    
    # ========================================================================
    # STEP 5: Drop old domain string columns
    # ========================================================================
    
    print("🗑️ Dropping old domain string columns...")
    
    op.drop_column('files', 'domain')
    op.drop_column('file_processing_jobs', 'domain')
    op.drop_column('embeddings', 'domain')
    op.drop_column('chat_sessions', 'domain')
    op.drop_column('classification_results', 'domain')
    op.drop_column('rag_executions', 'domain')
    op.drop_column('crawled_pages', 'domain')
    op.drop_column('connectors', 'domain')
    
    # ========================================================================
    # STEP 6: Update connectors table unique constraint
    # ========================================================================
    
    print("🔗 Updating connectors table unique constraint...")
    
    # Drop old unique constraint
    op.drop_constraint('uq_connectors_org_domain_name', 'connectors', type_='unique')
    
    # Create new unique constraint with domain_id
    op.create_unique_constraint('uq_connectors_org_domain_id_name', 'connectors', ['organization_id', 'domain_id', 'name'])
    
    print("✅ Migration completed successfully!")


def downgrade() -> None:
    """
    Rollback migration - restore domain string columns
    """
    
    print("🔄 Rolling back domain UUID migration...")
    
    # Get connection for data migration
    connection = op.get_bind()
    
    # ========================================================================
    # STEP 1: Add back domain string columns
    # ========================================================================
    
    print("📝 Adding back domain string columns...")
    
    op.add_column('files', sa.Column('domain', sa.String(50), nullable=True, default='general'))
    op.add_column('file_processing_jobs', sa.Column('domain', sa.String(50), nullable=True, default='general'))
    op.add_column('embeddings', sa.Column('domain', sa.String(50), nullable=True))
    op.add_column('chat_sessions', sa.Column('domain', sa.String(50), nullable=True, default='general'))
    op.add_column('classification_results', sa.Column('domain', sa.String(50), nullable=True))
    op.add_column('rag_executions', sa.Column('domain', sa.String(50), nullable=True))
    op.add_column('crawled_pages', sa.Column('domain', sa.String(50), nullable=True, default='general'))
    op.add_column('connectors', sa.Column('domain', sa.String(255), nullable=True))
    
    # ========================================================================
    # STEP 2: Populate domain string columns from domain_id
    # ========================================================================
    
    print("🔄 Populating domain string columns...")
    
    # Populate all tables with domain names from organization_domains
    tables = ['files', 'file_processing_jobs', 'embeddings', 'chat_sessions', 
              'classification_results', 'rag_executions', 'crawled_pages', 'connectors']
    
    for table in tables:
        connection.execute(text(f"""
            UPDATE {table} 
            SET domain = od.domain_name 
            FROM organization_domains od 
            WHERE {table}.domain_id = od.id
        """))
        
        # Set default 'general' for any missing values
        connection.execute(text(f"""
            UPDATE {table} 
            SET domain = 'general' 
            WHERE domain IS NULL
        """))
    
    # ========================================================================
    # STEP 3: Make domain columns non-nullable and set defaults
    # ========================================================================
    
    print("🔒 Making domain string columns non-nullable...")
    
    op.alter_column('files', 'domain', nullable=False, server_default='general')
    op.alter_column('file_processing_jobs', 'domain', nullable=False, server_default='general')
    op.alter_column('embeddings', 'domain', nullable=False)
    op.alter_column('chat_sessions', 'domain', nullable=False, server_default='general')
    op.alter_column('crawled_pages', 'domain', nullable=False, server_default='general')
    op.alter_column('connectors', 'domain', nullable=False)
    
    # ========================================================================
    # STEP 4: Drop domain_id columns and related constraints/indexes
    # ========================================================================
    
    print("🗑️ Dropping domain_id columns and constraints...")
    
    # Drop indexes first
    op.drop_index('idx_files_domain_id', 'files')
    op.drop_index('idx_files_org_domain', 'files')
    op.drop_index('idx_file_processing_jobs_domain_id', 'file_processing_jobs')
    op.drop_index('idx_file_processing_jobs_org_domain', 'file_processing_jobs')
    op.drop_index('idx_embeddings_domain_id', 'embeddings')
    op.drop_index('idx_embeddings_org_domain', 'embeddings')
    op.drop_index('idx_chat_sessions_domain_id', 'chat_sessions')
    op.drop_index('idx_chat_sessions_org_domain', 'chat_sessions')
    op.drop_index('idx_classification_results_domain_id', 'classification_results')
    op.drop_index('idx_classification_results_org_domain', 'classification_results')
    op.drop_index('idx_rag_executions_domain_id', 'rag_executions')
    op.drop_index('idx_rag_executions_org_domain', 'rag_executions')
    op.drop_index('idx_crawled_pages_domain_id', 'crawled_pages')
    op.drop_index('idx_crawled_pages_org_domain', 'crawled_pages')
    op.drop_index('idx_connectors_domain_id', 'connectors')
    op.drop_index('idx_connectors_org_domain_id', 'connectors')
    
    # Drop foreign key constraints
    op.drop_constraint('fk_files_domain_id', 'files', type_='foreignkey')
    op.drop_constraint('fk_file_processing_jobs_domain_id', 'file_processing_jobs', type_='foreignkey')
    op.drop_constraint('fk_embeddings_domain_id', 'embeddings', type_='foreignkey')
    op.drop_constraint('fk_chat_sessions_domain_id', 'chat_sessions', type_='foreignkey')
    op.drop_constraint('fk_classification_results_domain_id', 'classification_results', type_='foreignkey')
    op.drop_constraint('fk_rag_executions_domain_id', 'rag_executions', type_='foreignkey')
    op.drop_constraint('fk_crawled_pages_domain_id', 'crawled_pages', type_='foreignkey')
    op.drop_constraint('fk_connectors_domain_id', 'connectors', type_='foreignkey')
    
    # Drop domain_id columns
    op.drop_column('files', 'domain_id')
    op.drop_column('file_processing_jobs', 'domain_id')
    op.drop_column('embeddings', 'domain_id')
    op.drop_column('chat_sessions', 'domain_id')
    op.drop_column('classification_results', 'domain_id')
    op.drop_column('rag_executions', 'domain_id')
    op.drop_column('crawled_pages', 'domain_id')
    op.drop_column('connectors', 'domain_id')
    
    # ========================================================================
    # STEP 5: Restore original indexes and constraints
    # ========================================================================
    
    print("📈 Restoring original indexes and constraints...")
    
    # Restore connectors unique constraint
    op.drop_constraint('uq_connectors_org_domain_id_name', 'connectors', type_='unique')
    op.create_unique_constraint('uq_connectors_org_domain_name', 'connectors', ['organization_id', 'domain', 'name'])
    
    # Restore original connectors indexes
    op.create_index('idx_connectors_domain', 'connectors', ['domain'])
    op.create_index('idx_connectors_org_domain', 'connectors', ['organization_id', 'domain'])
    
    print("✅ Rollback completed successfully!") 