"""Add API/token usage monitoring tables (superadmin-only)

Revision ID: q8r9s0t1u2v3
Revises: p7q8r9s0t1u2
Create Date: 2026-09-23
"""
import sqlalchemy as sa
from alembic import op

revision = "q8r9s0t1u2v3"
down_revision = "p7q8r9s0t1u2"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_usage_events",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("service", sa.String(50), nullable=False),
        sa.Column("feature", sa.String(100), nullable=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("estimated_cost_usd", sa.Float, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="success"),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_api_usage_events_service", "api_usage_events", ["service"])
    op.create_index("ix_api_usage_events_created_at", "api_usage_events", ["created_at"])
    op.create_index("ix_usage_event_service_created", "api_usage_events", ["service", "created_at"])

    op.create_table(
        "api_usage_hourly",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("bucket_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("endpoint", sa.String(150), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("request_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("total_latency_ms", sa.BigInteger, nullable=False, server_default="0"),
        sa.UniqueConstraint("bucket_start", "endpoint", "method", name="uq_usage_hourly_bucket"),
    )
    op.create_index("ix_api_usage_hourly_bucket_start", "api_usage_hourly", ["bucket_start"])

    op.create_table(
        "usage_alert_config",
        sa.Column("id", sa.String(20), primary_key=True),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("spike_multiplier", sa.Float, nullable=False, server_default="3.0"),
        sa.Column("notification_channels", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
    )


def downgrade():
    op.drop_table("usage_alert_config")
    op.drop_table("api_usage_hourly")
    op.drop_table("api_usage_events")
