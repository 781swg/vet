"""doctor user telegram id bigint

Revision ID: 0003_doctor_user_telegram_bigint
Revises: 0002_webhook_events
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = "0003_doctor_user_telegram_bigint"
down_revision = "0002_webhook_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "doctor_users",
        "telegram_user_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "doctor_users",
        "telegram_user_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )

