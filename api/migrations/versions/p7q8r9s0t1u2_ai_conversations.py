"""Add AI assistant conversation/message/pending-action tables

Revision ID: p7q8r9s0t1u2
Revises: o6p7q8r9s0t1
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

revision = "p7q8r9s0t1u2"
down_revision = "o6p7q8r9s0t1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ai_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("page", sa.String(60), nullable=False, server_default="Overview"),
        sa.Column("is_archived", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_conversations_user_id", "ai_conversations", ["user_id"])
    op.create_index("ix_ai_conversations_is_archived", "ai_conversations", ["is_archived"])
    op.create_index("ix_ai_conv_user_active", "ai_conversations", ["user_id", "is_archived", "updated_at"])

    op.create_table(
        "ai_messages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36),
                  sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("contains_warning", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ai_messages_conversation_id", "ai_messages", ["conversation_id"])
    op.create_index("ix_ai_msg_conv_created", "ai_messages", ["conversation_id", "created_at"])

    op.create_table(
        "ai_pending_actions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(36),
                  sa.ForeignKey("ai_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("tool_name", sa.String(60), nullable=False),
        sa.Column("tool_input", sa.JSON, nullable=False),
        sa.Column("tool_use_id", sa.String(120), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("contains_warning", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("result", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_ai_pending_actions_conversation_id", "ai_pending_actions", ["conversation_id"])
    op.create_index("ix_ai_pending_actions_user_id", "ai_pending_actions", ["user_id"])
    op.create_index("ix_ai_pending_actions_status", "ai_pending_actions", ["status"])


def downgrade():
    op.drop_table("ai_pending_actions")
    op.drop_table("ai_messages")
    op.drop_table("ai_conversations")
