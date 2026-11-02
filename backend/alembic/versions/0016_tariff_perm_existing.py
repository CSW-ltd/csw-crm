"""settings.tariff ruxsati (managerlarga); mavjud shartnomalar buxgalter tasdig'iga qaytariladi

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-02 17:00:00
"""
from datetime import datetime, timezone

from alembic import context, op
import sqlalchemy as sa


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Qo'lda yoki Excel'dan kiritilgan (PR #18) va hali tasdiqlanmagan deb hisoblanishi kerak bo'lgan shartnomalar — buxgalter navbatiga
    op.execute("UPDATE contracts SET status = 'signed', approved_at = NULL, approved_by_id = NULL "
               "WHERE source IN ('manual', 'import') AND status = 'approved'")
    if context.is_offline_mode():
        return
    conn = op.get_bind()
    users = sa.table("users", sa.column("id", sa.Integer), sa.column("role", sa.String))
    perms = sa.table("user_permissions", sa.column("user_id", sa.Integer), sa.column("code", sa.String),
                     sa.column("created_at", sa.DateTime))
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    have = {u for (u,) in conn.execute(sa.select(perms.c.user_id).where(perms.c.code == "settings.tariff"))}
    rows = [{"user_id": uid, "code": "settings.tariff", "created_at": now}
            for (uid,) in conn.execute(sa.select(users.c.id).where(users.c.role == "manager")) if uid not in have]
    if rows:
        op.bulk_insert(perms, rows)


def downgrade() -> None:
    op.execute("DELETE FROM user_permissions WHERE code = 'settings.tariff'")
