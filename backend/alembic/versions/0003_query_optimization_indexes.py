"""Add composite and covering indexes for query optimization.

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-15
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_entities_type_status_created",
        "entities",
        ["type", "status", "created_at"],
    )
    op.create_index("ix_entities_owner_id", "entities", ["owner_id"])
    op.create_index("ix_entities_is_public", "entities", ["is_public"])
    op.create_index(
        "ix_entities_created_at_desc",
        "entities",
        [op.desc("created_at")],
    )

    op.create_index(
        "ix_chat_messages_session_created",
        "chat_messages",
        ["session_id", "created_at"],
    )
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"])

    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("ix_documents_owner_id", "documents", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_documents_owner_id", table_name="documents")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_chat_messages_session_created", table_name="chat_messages")
    op.drop_index("ix_entities_created_at_desc", table_name="entities")
    op.drop_index("ix_entities_is_public", table_name="entities")
    op.drop_index("ix_entities_owner_id", table_name="entities")
    op.drop_index("ix_entities_type_status_created", table_name="entities")
