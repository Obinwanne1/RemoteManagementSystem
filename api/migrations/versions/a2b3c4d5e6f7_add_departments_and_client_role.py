"""add departments table, department_id/customer_id to users, department_id to tickets

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-06-18 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'a2b3c4d5e6f7'
down_revision = 'f1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'departments',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('color', sa.String(7), nullable=False, server_default='#407E3C'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.String(36),
                                      sa.ForeignKey('departments.id'), nullable=True))
        batch_op.add_column(sa.Column('customer_id', sa.String(36),
                                      sa.ForeignKey('customers.id'), nullable=True))

    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.add_column(sa.Column('department_id', sa.String(36),
                                      sa.ForeignKey('departments.id'), nullable=True))


def downgrade():
    with op.batch_alter_table('tickets', schema=None) as batch_op:
        batch_op.drop_column('department_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_column('customer_id')
        batch_op.drop_column('department_id')

    op.drop_table('departments')
