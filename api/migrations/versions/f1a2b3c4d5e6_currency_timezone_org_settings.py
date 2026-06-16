"""Add currency and timezone to org_settings

Revision ID: f1a2b3c4d5e6
Revises: e6f7a8b9c0d1
Create Date: 2026-06-16 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'f1a2b3c4d5e6'
down_revision = 'e6f7a8b9c0d1'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('org_settings', sa.Column('currency', sa.String(3),  nullable=True, server_default='USD'))
    op.add_column('org_settings', sa.Column('timezone', sa.String(50), nullable=True, server_default='UTC'))


def downgrade():
    op.drop_column('org_settings', 'timezone')
    op.drop_column('org_settings', 'currency')
