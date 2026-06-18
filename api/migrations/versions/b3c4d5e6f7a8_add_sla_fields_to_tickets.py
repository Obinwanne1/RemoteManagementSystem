"""add sla fields to tickets

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "b3c4d5e6f7a8"
down_revision = "a2b3c4d5e6f7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(sa.Column("due_date", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("first_response_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("sla_breached", sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_column("sla_breached")
        batch_op.drop_column("first_response_at")
        batch_op.drop_column("due_date")
