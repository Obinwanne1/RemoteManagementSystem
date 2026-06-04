"""agentless device columns

Revision ID: f3e2d1c0b9a8
Revises: 93baa3927b0c
Create Date: 2026-06-04 00:00:00.000000

Adds is_agentless, device_type, vendor columns to devices table.
Makes customer_id nullable (agentless devices may not have a tenant yet).
"""
from alembic import op
import sqlalchemy as sa


revision = 'f3e2d1c0b9a8'
down_revision = '93baa3927b0c'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_agentless', sa.Boolean(),
                                      server_default='false', nullable=False))
        batch_op.add_column(sa.Column('device_type', sa.String(50),
                                      server_default='laptop', nullable=False))
        batch_op.add_column(sa.Column('vendor', sa.String(255), nullable=True))
        batch_op.alter_column('customer_id',
                              existing_type=sa.String(36),
                              nullable=True)


def downgrade():
    with op.batch_alter_table('devices', schema=None) as batch_op:
        batch_op.alter_column('customer_id',
                              existing_type=sa.String(36),
                              nullable=False)
        batch_op.drop_column('vendor')
        batch_op.drop_column('device_type')
        batch_op.drop_column('is_agentless')
