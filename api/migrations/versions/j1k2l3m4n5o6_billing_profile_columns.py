"""add billing profile columns to customers

Revision ID: j1k2l3m4n5o6
Revises: i0j1k2l3m4n5
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "j1k2l3m4n5o6"
down_revision = "i0j1k2l3m4n5"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("customers", sa.Column("billing_day", sa.Integer(), nullable=True))
    op.add_column("customers", sa.Column("per_device_rate", sa.Numeric(10, 2), nullable=True))
    op.add_column("customers", sa.Column("tax_rate", sa.Numeric(5, 4), nullable=True))


def downgrade():
    op.drop_column("customers", "billing_day")
    op.drop_column("customers", "per_device_rate")
    op.drop_column("customers", "tax_rate")
