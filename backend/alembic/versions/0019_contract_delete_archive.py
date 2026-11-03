"""Tugallanmagan shartnomani izoh bilan o'chirish (arxiv): deleted_at, delete_reason, archived_number

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-03 11:30:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0019'
down_revision = '0018'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("contracts") as b:
        b.add_column(sa.Column("deleted_at", sa.DateTime(), nullable=True))
        b.add_column(sa.Column("delete_reason", sa.String(500), nullable=True))
        b.add_column(sa.Column("archived_number", sa.String(90), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("contracts") as b:
        b.drop_column("archived_number")
        b.drop_column("delete_reason")
        b.drop_column("deleted_at")
