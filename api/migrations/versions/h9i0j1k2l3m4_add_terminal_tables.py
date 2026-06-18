"""add terminal tables

Revision ID: h9i0j1k2l3m4
Revises: f7a8b9c0d1e2
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "h9i0j1k2l3m4"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "terminal_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_terminal_sessions_device_id", "terminal_sessions", ["device_id"])
    op.create_index("ix_terminal_sessions_status", "terminal_sessions", ["status"])

    op.create_table(
        "terminal_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("terminal_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("picked_up_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_terminal_commands_session_id", "terminal_commands", ["session_id"])
    op.create_index("ix_terminal_commands_status", "terminal_commands", ["status"])

    op.create_table(
        "terminal_outputs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), primary_key=True, autoincrement=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("terminal_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("command_id", sa.String(36), sa.ForeignKey("terminal_commands.id", ondelete="SET NULL"), nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("stream", sa.String(10), nullable=False, server_default="stdout"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_terminal_outputs_session_id", "terminal_outputs", ["session_id"])


def downgrade():
    op.drop_table("terminal_outputs")
    op.drop_table("terminal_commands")
    op.drop_table("terminal_sessions")
