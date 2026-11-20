"""Schyot-faktura raqami yuborishda beriladi (har provider bo'yicha, yillik); yuborish usuli (sms/manual)

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-20 21:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0024'
down_revision = '0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("invoices") as b:
        b.alter_column("number", existing_type=sa.String(30), nullable=True)
        b.add_column(sa.Column("sent_via", sa.String(10), nullable=True))
    # Qoralamalar raqamsiz bo'ladi (raqam yuborishda beriladi); yuborilganlar eski raqamini saqlaydi
    op.execute("UPDATE invoices SET number = NULL WHERE status = 'draft'")
    op.execute("UPDATE invoices SET sent_via = 'sms' WHERE status = 'sent' AND sms_phone IS NOT NULL")
    op.create_table(
        "invoice_counters",
        sa.Column("provider_id", sa.Integer(), sa.ForeignKey("providers.id"), primary_key=True),
        sa.Column("year", sa.Integer(), primary_key=True),
        sa.Column("last_value", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_table("invoice_counters")
    expr = "'DRAFT-' || id" if op.get_bind().dialect.name == "sqlite" else "CONCAT('DRAFT-', id)"
    op.execute(f"UPDATE invoices SET number = {expr} WHERE number IS NULL")
    with op.batch_alter_table("invoices") as b:
        b.drop_column("sent_via")
        b.alter_column("number", existing_type=sa.String(30), nullable=False)
