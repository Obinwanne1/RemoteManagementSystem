"""Add consecutive_failures counter to PSA/MDM integrations (error-handling audit
Finding R6: neither had any circuit-breaker mechanism, so a permanently-broken
integration was retried forever with no automatic disable).

Revision ID: r9s0t1u2v3w4
Revises: q8r9s0t1u2v3
Create Date: 2026-09-24
"""
import sqlalchemy as sa
from alembic import op

revision = "r9s0t1u2v3w4"
down_revision = "q8r9s0t1u2v3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "psa_integrations",
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column(
        "mdm_integrations",
        sa.Column("consecutive_failures", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade():
    op.drop_column("mdm_integrations", "consecutive_failures")
    op.drop_column("psa_integrations", "consecutive_failures")
