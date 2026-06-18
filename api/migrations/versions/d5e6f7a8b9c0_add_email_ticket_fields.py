"""add email ticket fields

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("tickets") as batch_op:
        batch_op.add_column(sa.Column("email_thread_id", sa.String(500), nullable=True))
        batch_op.add_column(sa.Column("requester_email", sa.String(255), nullable=True))
        batch_op.add_column(sa.Column("requester_name", sa.String(255), nullable=True))
        batch_op.create_index("ix_tickets_email_thread_id", ["email_thread_id"], unique=False)

    with op.batch_alter_table("ticket_comments") as batch_op:
        batch_op.alter_column("author_id", existing_type=sa.String(36), nullable=True)
        batch_op.add_column(sa.Column("author_email", sa.String(255), nullable=True))


def downgrade():
    with op.batch_alter_table("ticket_comments") as batch_op:
        batch_op.drop_column("author_email")
        batch_op.alter_column("author_id", existing_type=sa.String(36), nullable=False)

    with op.batch_alter_table("tickets") as batch_op:
        batch_op.drop_index("ix_tickets_email_thread_id")
        batch_op.drop_column("requester_name")
        batch_op.drop_column("requester_email")
        batch_op.drop_column("email_thread_id")
