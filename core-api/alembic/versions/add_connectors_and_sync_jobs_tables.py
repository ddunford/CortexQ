"""Add connectors and sync_jobs tables

Revision ID: add_connectors_sync_jobs
Revises: 649e18af6ae8
Create Date: 2025-05-26 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'add_connectors_sync_jobs'
down_revision: Union[str, None] = '649e18af6ae8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create connectors table
    op.create_table('connectors',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('connector_type', sa.String(50), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), nullable=False, default=True),
        sa.Column('auth_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('sync_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('mapping_config', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('last_sync_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('last_sync_status', sa.String(50), nullable=True),
        sa.Column('sync_error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('organization_id', 'domain', 'name', name='uq_connectors_org_domain_name')
    )
    
    # Create sync_jobs table
    op.create_table('sync_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False, default=sa.text('gen_random_uuid()')),
        sa.Column('connector_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('organization_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('started_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(), nullable=True),
        sa.Column('records_processed', sa.Integer(), nullable=False, default=0),
        sa.Column('records_created', sa.Integer(), nullable=False, default=0),
        sa.Column('records_updated', sa.Integer(), nullable=False, default=0),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), nullable=False, default=sa.func.now()),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['connector_id'], ['connectors.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['organization_id'], ['organizations.id'], ondelete='CASCADE')
    )
    
    # Create indexes for connectors table
    op.create_index('idx_connectors_organization_id', 'connectors', ['organization_id'])
    op.create_index('idx_connectors_domain', 'connectors', ['domain'])
    op.create_index('idx_connectors_type', 'connectors', ['connector_type'])
    op.create_index('idx_connectors_enabled', 'connectors', ['is_enabled'])
    op.create_index('idx_connectors_org_domain', 'connectors', ['organization_id', 'domain'])
    op.create_index('idx_connectors_last_sync', 'connectors', ['last_sync_at'])
    
    # Create indexes for sync_jobs table
    op.create_index('idx_sync_jobs_connector_id', 'sync_jobs', ['connector_id'])
    op.create_index('idx_sync_jobs_organization_id', 'sync_jobs', ['organization_id'])
    op.create_index('idx_sync_jobs_status', 'sync_jobs', ['status'])
    op.create_index('idx_sync_jobs_created_at', 'sync_jobs', ['created_at'])
    op.create_index('idx_sync_jobs_connector_status', 'sync_jobs', ['connector_id', 'status'])


def downgrade() -> None:
    # Drop indexes for sync_jobs table
    op.drop_index('idx_sync_jobs_connector_status', 'sync_jobs')
    op.drop_index('idx_sync_jobs_created_at', 'sync_jobs')
    op.drop_index('idx_sync_jobs_status', 'sync_jobs')
    op.drop_index('idx_sync_jobs_organization_id', 'sync_jobs')
    op.drop_index('idx_sync_jobs_connector_id', 'sync_jobs')
    
    # Drop indexes for connectors table
    op.drop_index('idx_connectors_last_sync', 'connectors')
    op.drop_index('idx_connectors_org_domain', 'connectors')
    op.drop_index('idx_connectors_enabled', 'connectors')
    op.drop_index('idx_connectors_type', 'connectors')
    op.drop_index('idx_connectors_domain', 'connectors')
    op.drop_index('idx_connectors_organization_id', 'connectors')
    
    # Drop tables
    op.drop_table('sync_jobs')
    op.drop_table('connectors') 