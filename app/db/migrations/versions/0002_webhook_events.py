"""webhook events idempotency

Revision ID: 0002_webhook_events
Revises: 0001_initial
Create Date: 2026-05-11
"""
from alembic import op
import sqlalchemy as sa


revision = "0002_webhook_events"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("channel", sa.String(32), nullable=False),
        sa.Column("idempotency_key", sa.String(255), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("raw_payload", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True)),
        sa.Column("processed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("channel", "idempotency_key", name="uq_webhook_events_channel_key"),
    )
    op.create_index("ix_webhook_events_channel", "webhook_events", ["channel"])
    op.create_index("ix_webhook_events_idempotency_key", "webhook_events", ["idempotency_key"])


def downgrade() -> None:
    op.drop_index("ix_webhook_events_idempotency_key", table_name="webhook_events")
    op.drop_index("ix_webhook_events_channel", table_name="webhook_events")
    op.drop_table("webhook_events")

