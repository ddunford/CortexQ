"""Add MinIO support to files table

Revision ID: add_minio_support
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_minio_support'
down_revision = '4e6534661f68'  # Initial database schema
branch_labels = None
depends_on = None


def upgrade():
    # Add storage_type column to files table
    op.add_column('files', sa.Column('storage_type', sa.String(50), nullable=True, default='local'))
    
    # Add object_key column for MinIO object keys
    op.add_column('files', sa.Column('object_key', sa.String(500), nullable=True))
    
    # Add storage_url column for presigned URLs
    op.add_column('files', sa.Column('storage_url', sa.Text(), nullable=True))
    
    # Update existing records to use 'local' storage type
    op.execute("UPDATE files SET storage_type = 'local' WHERE storage_type IS NULL")
    
    # Make storage_type non-nullable after setting default values
    op.alter_column('files', 'storage_type', nullable=False)
    
    # Add index for object_key for faster lookups
    op.create_index('idx_files_object_key', 'files', ['object_key'])
    
    # Add index for storage_type
    op.create_index('idx_files_storage_type', 'files', ['storage_type'])


def downgrade():
    # Remove indexes
    op.drop_index('idx_files_storage_type', 'files')
    op.drop_index('idx_files_object_key', 'files')
    
    # Remove columns
    op.drop_column('files', 'storage_url')
    op.drop_column('files', 'object_key')
    op.drop_column('files', 'storage_type') 