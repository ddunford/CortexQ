"""merge heads

Revision ID: af0bea9b8304
Revises: 07a4f3f496a9, migrate_domain_refs_to_uuid
Create Date: 2025-05-26 20:37:15.993536

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'af0bea9b8304'
down_revision: Union[str, None] = ('07a4f3f496a9', 'migrate_domain_refs_to_uuid')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
