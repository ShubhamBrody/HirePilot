"""add subscriptions table

Revision ID: a7b3c9d1e5f2
Revises: d5e8f2a1b3c7
Create Date: 2025-01-01 00:04:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision = "a7b3c9d1e5f2"
down_revision = "d5e8f2a1b3c7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(50), nullable=False, server_default="free"),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column("price_monthly", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("billing_cycle", sa.String(20), nullable=False, server_default="monthly"),
        sa.Column("max_resumes", sa.Integer, nullable=False, server_default="3"),
        sa.Column("max_applications_per_day", sa.Integer, nullable=False, server_default="5"),
        sa.Column("max_job_scrapes_per_day", sa.Integer, nullable=False, server_default="10"),
        sa.Column("ai_tailoring_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("recruiter_outreach_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("autonomous_mode_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("mock_card_last4", sa.String(4), nullable=True),
        sa.Column("mock_next_billing_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_subscriptions_user_id", table_name="subscriptions")
    op.drop_table("subscriptions")
