"""Korxona koordinatasining manbasi: legal (shartnomada yurist) | driver (birinchi tashrif) | manager (tasdiq/qo'lda)

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-06 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("customers") as b:
        b.add_column(sa.Column("location_source", sa.String(10), nullable=True))
    # Mavjud ma'lumot: kutilayotgan nuqtalar — haydovchining birinchi tashrifidan, tasdiqlanganlari — manager
    op.execute("UPDATE customers SET location_source = 'driver' WHERE location_status = 'pending'")
    op.execute("UPDATE customers SET location_source = 'manager' WHERE location_status = 'confirmed'")


def downgrade() -> None:
    with op.batch_alter_table("customers") as b:
        b.drop_column("location_source")
