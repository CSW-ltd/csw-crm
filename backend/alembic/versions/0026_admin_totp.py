"""Admin 2FA (TOTP): users.totp_*, zaxira kodlar jadvali

Revision ID: 0026
Revises: 0025
Create Date: 2026-11-23 15:00:00
"""
from alembic import op
import sqlalchemy as sa


revision = '0026'
down_revision = '0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as b:
        b.add_column(sa.Column("totp_secret_enc", sa.String(255), nullable=True))
        b.add_column(sa.Column("totp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
        b.add_column(sa.Column("totp_last_step", sa.Integer(), nullable=True))
    op.create_table(
        "user_backup_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("used_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_backup_codes_user_id", "user_backup_codes", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_user_backup_codes_user_id", table_name="user_backup_codes")
    op.drop_table("user_backup_codes")
    with op.batch_alter_table("users") as b:
        b.drop_column("totp_last_step")
        b.drop_column("totp_enabled")
        b.drop_column("totp_secret_enc")
