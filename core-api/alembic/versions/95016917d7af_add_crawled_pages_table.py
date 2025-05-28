"""add_crawled_pages_table

Revision ID: 95016917d7af
Revises: af0bea9b8304
Create Date: 2025-05-26 22:37:49.444148

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '95016917d7af'
down_revision: Union[str, None] = 'af0bea9b8304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create crawled_pages table for web scraper results
    op.create_table(
        'crawled_pages',
        sa.Column('id', sa.UUID(as_uuid=True), primary_key=True, default=sa.text('gen_random_uuid()')),
        sa.Column('connector_id', sa.UUID(as_uuid=True), sa.ForeignKey('connectors.id', ondelete='CASCADE'), nullable=False),
        sa.Column('organization_id', sa.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('domain', sa.String(255), nullable=False),
        sa.Column('url', sa.Text, nullable=False),
        sa.Column('url_hash', sa.String(32), nullable=False),  # MD5 hash of URL for uniqueness
        sa.Column('title', sa.Text, nullable=True),
        sa.Column('content', sa.Text, nullable=True),
        sa.Column('metadata', sa.JSON, nullable=True),
        sa.Column('first_crawled', sa.TIMESTAMP, nullable=False, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('last_crawled', sa.TIMESTAMP, nullable=False, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('content_hash', sa.String(32), nullable=True),  # MD5 hash of content for change detection
        sa.Column('word_count', sa.Integer, nullable=True),
        sa.Column('status', sa.String(50), nullable=False, default='success'),  # success, failed, skipped
        sa.Column('error_message', sa.Text, nullable=True),
        sa.Column('depth', sa.Integer, nullable=False, default=0),  # Crawl depth from start URL
        sa.Column('content_type', sa.String(100), nullable=True),
        sa.Column('file_size', sa.Integer, nullable=True),  # Size in bytes
        sa.Column('last_modified', sa.TIMESTAMP, nullable=True),  # From HTTP headers if available
        sa.Column('created_at', sa.TIMESTAMP, nullable=False, default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.TIMESTAMP, nullable=False, default=sa.text('CURRENT_TIMESTAMP'))
    )
    
    # Create indexes for performance
    op.create_index('idx_crawled_pages_connector_id', 'crawled_pages', ['connector_id'])
    op.create_index('idx_crawled_pages_organization_id', 'crawled_pages', ['organization_id'])
    op.create_index('idx_crawled_pages_url_hash', 'crawled_pages', ['url_hash'])
    op.create_index('idx_crawled_pages_last_crawled', 'crawled_pages', ['last_crawled'])
    op.create_index('idx_crawled_pages_status', 'crawled_pages', ['status'])
    op.create_index('idx_crawled_pages_domain', 'crawled_pages', ['domain'])
    
    # Create unique constraint on organization + connector + url_hash
    op.create_unique_constraint(
        'uq_crawled_pages_org_connector_url',
        'crawled_pages',
        ['organization_id', 'connector_id', 'url_hash']
    )


def downgrade() -> None:
    # Drop indexes first
    op.drop_index('idx_crawled_pages_connector_id', 'crawled_pages')
    op.drop_index('idx_crawled_pages_organization_id', 'crawled_pages')
    op.drop_index('idx_crawled_pages_url_hash', 'crawled_pages')
    op.drop_index('idx_crawled_pages_last_crawled', 'crawled_pages')
    op.drop_index('idx_crawled_pages_status', 'crawled_pages')
    op.drop_index('idx_crawled_pages_domain', 'crawled_pages')
    
    # Drop constraint
    op.drop_constraint('uq_crawled_pages_org_connector_url', 'crawled_pages', type_='unique')
    
    # Drop table
    op.drop_table('crawled_pages')
