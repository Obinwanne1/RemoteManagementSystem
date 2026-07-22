"""add performance indexes for summary and list queries

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-07-22
"""
from alembic import op

revision = "m4n5o6p7q8r9"
down_revision = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade():
    # alerts — status + triggered_at used in every summary + list query
    op.create_index("ix_alerts_status", "alerts", ["status"], if_not_exists=True)
    op.create_index("ix_alerts_triggered_at", "alerts", ["triggered_at"], if_not_exists=True)
    op.create_index("ix_alerts_severity", "alerts", ["severity"], if_not_exists=True)
    op.create_index("ix_alerts_device_id_status", "alerts", ["device_id", "status"], if_not_exists=True)

    # devices — is_online used in dashboard summary aggregate
    op.create_index("ix_devices_is_online", "devices", ["is_online"], if_not_exists=True)
    op.create_index("ix_devices_status", "devices", ["status"], if_not_exists=True)

    # tickets — priority, sla_breached, assignee_id used in summary aggregates
    op.create_index("ix_tickets_priority", "tickets", ["priority"], if_not_exists=True)
    op.create_index("ix_tickets_sla_breached", "tickets", ["sla_breached"], if_not_exists=True)
    op.create_index("ix_tickets_assignee_id", "tickets", ["assignee_id"], if_not_exists=True)
    op.create_index("ix_tickets_customer_id", "tickets", ["customer_id"], if_not_exists=True)

    # audit_log — created_at used in activity feed ORDER BY
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"], if_not_exists=True)


def downgrade():
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_index("ix_tickets_customer_id", table_name="tickets")
    op.drop_index("ix_tickets_assignee_id", table_name="tickets")
    op.drop_index("ix_tickets_sla_breached", table_name="tickets")
    op.drop_index("ix_tickets_priority", table_name="tickets")
    op.drop_index("ix_devices_status", table_name="devices")
    op.drop_index("ix_devices_is_online", table_name="devices")
    op.drop_index("ix_alerts_device_id_status", table_name="alerts")
    op.drop_index("ix_alerts_severity", table_name="alerts")
    op.drop_index("ix_alerts_triggered_at", table_name="alerts")
    op.drop_index("ix_alerts_status", table_name="alerts")
