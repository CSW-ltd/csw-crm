"""Mavjud shartnomada qo'lda narx: contracts.tariff_price, contracts.price_reason; legal'larga customers.existing_price

Revision ID: 0018
Revises: 0017
Create Date: 2026-11-03 10:30:00
"""
from datetime import datetime, timezone

from alembic import context, op
import sqlalchemy as sa


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("contracts") as b:
        b.add_column(sa.Column("tariff_price", sa.Numeric(14, 2), nullable=True))
        b.add_column(sa.Column("price_reason", sa.String(255), nullable=True))
    if context.is_offline_mode():
        return
    conn = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("role", sa.String))
    perms = sa.table("user_permissions", sa.column("user_id", sa.Integer), sa.column("code", sa.String),
                     sa.column("created_at", sa.DateTime))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    have = {u for (u,) in conn.execute(sa.select(perms.c.user_id).where(perms.c.code == "customers.existing_price"))}
    rows = [{"user_id": uid, "code": "customers.existing_price", "created_at": now}
            for (uid,) in conn.execute(sa.select(users.c.id).where(users.c.role == "legal")) if uid not in have]
    if rows:
        op.bulk_insert(perms, rows)


def downgrade() -> None:
    op.execute("DELETE FROM user_permissions WHERE code = 'customers.existing_price'")
    with op.batch_alter_table("contracts") as b:
        b.drop_column("price_reason")
        b.drop_column("tariff_price")
