"""Update vector dimension from 768 to 3072 for gemini-embedding-001.

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # No-op: 0001 already creates the embedding column as vector(3072) with no
    # HNSW index (3072 dims exceed pgvector's 2000-dim index limit). Kept to
    # preserve the revision chain.
    pass


def downgrade() -> None:
    pass
