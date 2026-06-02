"""add composite indexes for performance

Revision ID: 2c8f1d3e9a4b
Revises: d746c05420bd
Create Date: 2026-06-02 12:00:00.000000

"""
from alembic import op

revision = '2c8f1d3e9a4b'
down_revision = 'd746c05420bd'
branch_labels = None
depends_on = None


def upgrade():
    # device_metrics: latest-metric-per-device queries use (device_id, id DESC)
    op.create_index(
        'ix_device_metrics_device_collected_at',
        'device_metrics', ['device_id', 'collected_at'],
    )
    # devices: filter by customer + online status
    op.create_index(
        'ix_devices_customer_online',
        'devices', ['customer_id', 'is_online'],
    )
    # alerts: cooldown checks and list filtering
    op.create_index(
        'ix_alerts_device_status',
        'alerts', ['device_id', 'status'],
    )
    # script_runs: agent task polling
    op.create_index(
        'ix_script_runs_device_status',
        'script_runs', ['device_id', 'status'],
    )
    # patch_records: patch status filtering
    op.create_index(
        'ix_patch_records_device_status',
        'patch_records', ['device_id', 'status'],
    )
    # tickets: dashboard count queries
    op.create_index(
        'ix_tickets_customer_status',
        'tickets', ['customer_id', 'status'],
    )


def downgrade():
    op.drop_index('ix_tickets_customer_status', table_name='tickets')
    op.drop_index('ix_patch_records_device_status', table_name='patch_records')
    op.drop_index('ix_script_runs_device_status', table_name='script_runs')
    op.drop_index('ix_alerts_device_status', table_name='alerts')
    op.drop_index('ix_devices_customer_online', table_name='devices')
    op.drop_index('ix_device_metrics_device_collected_at', table_name='device_metrics')
