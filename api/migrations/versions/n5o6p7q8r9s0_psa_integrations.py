"""Add PSA integration tables (ConnectWise + Autotask)

Revision ID: n5o6p7q8r9s0
Revises: m4n5o6p7q8r9
Create Date: 2026-07-23
"""
import sqlalchemy as sa
from alembic import op

revision = "n5o6p7q8r9s0"
down_revision = "m4n5o6p7q8r9"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "psa_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(30), nullable=False),
        sa.Column("api_url", sa.String(500), nullable=False),
        sa.Column("company_id", sa.String(255), nullable=True),
        sa.Column("client_id", sa.String(500), nullable=False),
        sa.Column("client_secret_enc", sa.Text, nullable=False),
        sa.Column("site_name", sa.String(255), nullable=True),
        sa.Column("sync_tickets", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sync_companies", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sync_configs", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "psa_company_maps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("psa_integration_id", sa.String(36),
                  sa.ForeignKey("psa_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(36),
                  sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("psa_company_id", sa.String(100), nullable=False),
        sa.Column("psa_company_name", sa.String(255), nullable=True),
        sa.Column("synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_psa_company_maps_integration", "psa_company_maps", ["psa_integration_id"])
    op.create_index("ix_psa_company_maps_customer", "psa_company_maps", ["customer_id"])
    op.create_unique_constraint(
        "uq_psa_company_map", "psa_company_maps",
        ["psa_integration_id", "customer_id"],
    )

    op.create_table(
        "psa_ticket_maps",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("psa_integration_id", sa.String(36),
                  sa.ForeignKey("psa_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ticket_id", sa.String(36),
                  sa.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("psa_ticket_id", sa.String(100), nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("sync_error", sa.Text, nullable=True),
    )
    op.create_index("ix_psa_ticket_maps_integration", "psa_ticket_maps", ["psa_integration_id"])
    op.create_index("ix_psa_ticket_maps_ticket", "psa_ticket_maps", ["ticket_id"])
    op.create_unique_constraint(
        "uq_psa_ticket_map", "psa_ticket_maps",
        ["psa_integration_id", "ticket_id"],
    )


def downgrade():
    op.drop_table("psa_ticket_maps")
    op.drop_table("psa_company_maps")
    op.drop_table("psa_integrations")
