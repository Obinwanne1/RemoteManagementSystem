"""add stripe fields to invoices

Revision ID: f7a8b9c0d1e2
Revises: d5e6f7a8b9c0
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "f7a8b9c0d1e2"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.add_column(sa.Column("stripe_checkout_session_id", sa.String(200), nullable=True))
        batch_op.add_column(sa.Column("stripe_payment_intent_id", sa.String(200), nullable=True))


def downgrade():
    with op.batch_alter_table("invoices") as batch_op:
        batch_op.drop_column("stripe_payment_intent_id")
        batch_op.drop_column("stripe_checkout_session_id")
