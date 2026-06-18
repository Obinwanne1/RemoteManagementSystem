"""add missing indexes

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-06-18
"""
from alembic import op

revision = "c4d5e6f7a8b9"
down_revision = "b3c4d5e6f7a8"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_tickets_status", "tickets", ["status"])
    op.create_index("ix_tickets_updated_at", "tickets", ["updated_at"])
    op.create_index("ix_devices_last_seen", "devices", ["last_seen"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])


def downgrade():
    op.drop_index("ix_audit_log_resource_type", table_name="audit_log")
    op.drop_index("ix_devices_last_seen", table_name="devices")
    op.drop_index("ix_tickets_updated_at", table_name="tickets")
    op.drop_index("ix_tickets_status", table_name="tickets")
