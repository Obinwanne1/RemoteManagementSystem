"""add sla_policies table

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-07-13
"""
from alembic import op
import sqlalchemy as sa

revision = "k2l3m4n5o6p7"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sla_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True, index=True),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("response_hours", sa.Integer(), nullable=False),
        sa.Column("resolution_hours", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("customer_id", "priority", name="uq_sla_customer_priority"),
    )
    # Seed global defaults (customer_id=NULL)
    op.execute("""
        INSERT INTO sla_policies (id, customer_id, priority, response_hours, resolution_hours, created_at)
        VALUES
          (gen_random_uuid()::text, NULL, 'critical', 1,  4,  NOW()),
          (gen_random_uuid()::text, NULL, 'high',     4,  8,  NOW()),
          (gen_random_uuid()::text, NULL, 'medium',   8,  24, NOW()),
          (gen_random_uuid()::text, NULL, 'low',      24, 72, NOW())
    """)


def downgrade():
    op.drop_table("sla_policies")
