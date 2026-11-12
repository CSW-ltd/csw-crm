"""Mavjud kontragent bo'yicha so'rovlar: qo'shimcha shartnoma (buxgalter), yangi filial va manzil o'zgartirish (GPS)

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-10 18:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0022'
down_revision = '0021'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "contract_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("status", sa.String(10), nullable=False, server_default="new"),
        sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False),
        sa.Column("contract_id", sa.Integer(), sa.ForeignKey("contracts.id"), nullable=True),
        sa.Column("district_id", sa.Integer(), sa.ForeignKey("districts.id"), nullable=False),
        sa.Column("note", sa.String(500), nullable=True),
        sa.Column("data", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("handled_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_contract_requests_kind", "contract_requests", ["kind"])
    op.create_index("ix_contract_requests_status", "contract_requests", ["status"])
    op.create_index("ix_contract_requests_customer_id", "contract_requests", ["customer_id"])
    op.create_index("ix_contract_requests_district_id", "contract_requests", ["district_id"])


def downgrade() -> None:
    op.drop_table("contract_requests")
