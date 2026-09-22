"""Add MDM integration + mobile enrollment tables (Android Management API)

Revision ID: o6p7q8r9s0t1
Revises: n5o6p7q8r9s0
Create Date: 2026-09-22
"""
import sqlalchemy as sa
from alembic import op

revision = "o6p7q8r9s0t1"
down_revision = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "mdm_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("type", sa.String(20), nullable=False, server_default="android"),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("project_id", sa.String(255), nullable=True),
        sa.Column("enterprise_id", sa.String(255), nullable=True),
        sa.Column("service_account_json_enc", sa.Text, nullable=True),
        sa.Column("default_policy_name", sa.String(255), nullable=True),
        sa.Column("pubsub_topic", sa.String(255), nullable=True),
        sa.Column("apple_push_cert_enc", sa.Text, nullable=True),
        sa.Column("apple_topic", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mdm_integrations_customer", "mdm_integrations", ["customer_id"])

    op.create_table(
        "mobile_enrollments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("mdm_integration_id", sa.String(36),
                  sa.ForeignKey("mdm_integrations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", sa.String(36),
                  sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True, unique=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id"), nullable=True),
        sa.Column("android_enterprise_device_name", sa.String(500), nullable=True),
        sa.Column("enrollment_token", sa.String(500), nullable=True),
        sa.Column("enrollment_token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ownership_type", sa.String(20), nullable=False, server_default="byod"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("consent_given_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("consent_text_version", sa.String(50), nullable=True),
        sa.Column("consent_ip_address", sa.String(45), nullable=True),
        sa.Column("policy_name", sa.String(255), nullable=True),
        sa.Column("last_policy_sync_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status_report_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_compliant", sa.Boolean, nullable=True),
        sa.Column("non_compliance_details", sa.JSON, nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_mobile_enrollments_integration", "mobile_enrollments", ["mdm_integration_id"])
    op.create_index("ix_mobile_enrollments_device", "mobile_enrollments", ["device_id"])
    op.create_index("ix_mobile_enrollments_customer", "mobile_enrollments", ["customer_id"])


def downgrade():
    op.drop_table("mobile_enrollments")
    op.drop_table("mdm_integrations")
