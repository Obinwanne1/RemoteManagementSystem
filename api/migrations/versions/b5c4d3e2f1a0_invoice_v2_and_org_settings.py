"""Invoice v2 columns + org_settings table

Revision ID: b5c4d3e2f1a0
Revises: e5d4c3b2a1f0
Create Date: 2026-06-05 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

revision = 'b5c4d3e2f1a0'
down_revision = 'e5d4c3b2a1f0'
branch_labels = None
depends_on = None


def upgrade():
    # Add new columns to invoices table
    op.add_column('invoices', sa.Column('invoice_number', sa.String(20), nullable=True))
    op.add_column('invoices', sa.Column('due_date', sa.DateTime(timezone=True), nullable=True))
    op.add_column('invoices', sa.Column('tax_rate', sa.Numeric(5, 4), nullable=True, server_default='0'))
    op.add_column('invoices', sa.Column('notes', sa.Text(), nullable=True))

    op.create_index('ix_invoices_invoice_number', 'invoices', ['invoice_number'], unique=True)

    # Create org_settings singleton table
    op.create_table(
        'org_settings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('company_name', sa.String(255), nullable=True, server_default=''),
        sa.Column('company_address', sa.Text(), nullable=True, server_default=''),
        sa.Column('company_email', sa.String(255), nullable=True, server_default=''),
        sa.Column('company_phone', sa.String(50), nullable=True, server_default=''),
        sa.Column('logo_data', sa.Text(), nullable=True),
        sa.Column('payment_terms', sa.String(100), nullable=True, server_default='Net 30'),
        sa.Column('bank_details', sa.Text(), nullable=True, server_default=''),
        sa.Column('footer_notes', sa.Text(), nullable=True, server_default='Thank you for your business!'),
    )


def downgrade():
    op.drop_table('org_settings')
    op.drop_index('ix_invoices_invoice_number', table_name='invoices')
    op.drop_column('invoices', 'notes')
    op.drop_column('invoices', 'tax_rate')
    op.drop_column('invoices', 'due_date')
    op.drop_column('invoices', 'invoice_number')
