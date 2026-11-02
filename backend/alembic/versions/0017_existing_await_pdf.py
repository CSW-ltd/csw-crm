"""Mavjud shartnomalar: asl PDF'siz kiritilganlar «Tugallanmagan»ga (PDF kutilmoqda) qaytariladi

Revision ID: 0017
Revises: 0016
Create Date: 2026-11-02 19:30:00
"""
from alembic import op


revision = '0017'
down_revision = '0016'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE contracts SET status = 'draft', is_active = 0, signed_at = NULL "
               "WHERE source IN ('manual', 'import') AND status = 'signed' AND scan_key IS NULL")


def downgrade() -> None:
    op.execute("UPDATE contracts SET status = 'signed', is_active = 1 "
               "WHERE source IN ('manual', 'import') AND status = 'draft' AND number IS NOT NULL")
