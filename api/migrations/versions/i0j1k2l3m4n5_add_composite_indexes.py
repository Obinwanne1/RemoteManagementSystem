"""add composite indexes for query performance

Revision ID: i0j1k2l3m4n5
Revises: h9i0j1k2l3m4
Create Date: 2026-07-13

Most composite indexes already exist in the DB from earlier migrations.
Only ix_devices_customer_status is missing.
"""
from alembic import op

revision = "i0j1k2l3m4n5"
down_revision = "h9i0j1k2l3m4"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index("ix_devices_customer_status", "devices", ["customer_id", "status"])


def downgrade():
    op.drop_index("ix_devices_customer_status", table_name="devices")
