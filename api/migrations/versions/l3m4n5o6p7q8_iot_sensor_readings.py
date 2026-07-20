"""add device_sensor_readings table

Revision ID: l3m4n5o6p7q8
Revises: k2l3m4n5o6p7
Create Date: 2026-07-18
"""
from alembic import op
import sqlalchemy as sa

revision = "l3m4n5o6p7q8"
down_revision = "k2l3m4n5o6p7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "device_sensor_readings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.String(36), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sensor_type", sa.String(50), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(20), nullable=True),
        sa.Column("channel", sa.String(50), nullable=True),
        sa.Column("source", sa.String(20), nullable=True),
    )
    op.create_index("ix_sensor_readings_device_time", "device_sensor_readings",
                    ["device_id", "collected_at"])
    op.create_index("ix_sensor_readings_customer_type_time", "device_sensor_readings",
                    ["customer_id", "sensor_type", "collected_at"])


def downgrade():
    op.drop_index("ix_sensor_readings_customer_type_time", table_name="device_sensor_readings")
    op.drop_index("ix_sensor_readings_device_time", table_name="device_sensor_readings")
    op.drop_table("device_sensor_readings")
