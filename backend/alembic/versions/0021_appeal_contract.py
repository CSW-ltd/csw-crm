"""Yangi korxona murojaati → shartnoma: appeals.contract_id (korxona murojaatda yaratilmaydi, shartnoma kontragentidan shakllanadi)

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-10 12:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0021'
down_revision = '0020'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("appeals") as b:
        b.add_column(sa.Column("contract_id", sa.Integer(), nullable=True))
        b.create_foreign_key("fk_appeals_contract_id", "contracts", ["contract_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("appeals") as b:
        b.drop_constraint("fk_appeals_contract_id", type_="foreignkey")
        b.drop_column("contract_id")
