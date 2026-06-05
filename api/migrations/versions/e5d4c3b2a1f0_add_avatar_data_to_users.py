"""add avatar_data to users

Revision ID: e5d4c3b2a1f0
Revises: 2c8f1d3e9a4b
Create Date: 2026-06-05 00:00:00.000000

Adds avatar_data (Text, nullable) column to users table.
Stores base64-encoded PNG avatar image.
"""
from alembic import op
import sqlalchemy as sa


revision = 'e5d4c3b2a1f0'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('avatar_data', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('avatar_data')
