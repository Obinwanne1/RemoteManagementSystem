"""make network_scans.customer_id nullable

Revision ID: a1b2c3d4e5f6
Revises: f3e2d1c0b9a8
Create Date: 2026-06-04

"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'f3e2d1c0b9a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('network_scans') as batch_op:
        batch_op.alter_column('customer_id', nullable=True, existing_type=sa.String(36))


def downgrade():
    with op.batch_alter_table('network_scans') as batch_op:
        batch_op.alter_column('customer_id', nullable=False, existing_type=sa.String(36))
