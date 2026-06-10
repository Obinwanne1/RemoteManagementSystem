"""White-label branding columns on org_settings

Revision ID: e6f7a8b9c0d1
Revises: d2e3f4a5b6c7
Create Date: 2026-06-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'e6f7a8b9c0d1'
down_revision = 'd2e3f4a5b6c7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('org_settings', sa.Column('app_name',      sa.String(100), nullable=True, server_default='RMM System'))
    op.add_column('org_settings', sa.Column('tagline',       sa.String(200), nullable=True, server_default='Remote Monitoring & Management'))
    op.add_column('org_settings', sa.Column('primary_color', sa.String(7),   nullable=True, server_default='#407E3C'))


def downgrade():
    op.drop_column('org_settings', 'primary_color')
    op.drop_column('org_settings', 'tagline')
    op.drop_column('org_settings', 'app_name')
