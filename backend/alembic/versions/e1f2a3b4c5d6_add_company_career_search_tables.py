"""add company career search tables

Revision ID: e1f2a3b4c5d6
Revises: a7b3c9d1e5f2
Create Date: 2026-03-21 12:00:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "a7b3c9d1e5f2"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # ── target_companies table ───────────────────────────────────
    op.create_table(
        "target_companies",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("career_page_url", sa.String(1000), nullable=True),
        sa.Column(
            "url_discovery_method",
            sa.Enum("ai_discovered", "user_provided", "verified", name="urldiscoverymethod"),
            nullable=True,
        ),
        sa.Column("url_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("scrape_frequency_hours", sa.Integer(), nullable=False, server_default="12"),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_scrape_status",
            sa.Enum("success", "failed", "partial", "never", name="scrapestatus"),
            nullable=False,
            server_default="never",
        ),
        sa.Column("last_scrape_error", sa.Text(), nullable=True),
        sa.Column("jobs_found_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("scrape_strategy", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "company_name", name="uq_user_company"),
    )

    # ── company_scraping_logs table ──────────────────────────────
    op.create_table(
        "company_scraping_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "target_company_id",
            UUID(as_uuid=True),
            sa.ForeignKey("target_companies.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failed", "partial", name="scrapingrunstatus"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("jobs_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("new_jobs_saved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "error_type",
            sa.Enum(
                "timeout", "blocked", "structure_change", "network",
                "captcha", "auth_required", "other",
                name="scrapingerrortype",
            ),
            nullable=True,
        ),
        sa.Column("page_url_used", sa.String(1000), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("strategy_used", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ── New columns on users table ───────────────────────────────
    op.add_column(
        "users",
        sa.Column("auto_apply_threshold", sa.Float(), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column(
            "company_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )
    op.add_column(
        "users",
        sa.Column(
            "linkedin_search_enabled",
            sa.Boolean(),
            nullable=False,
            server_default="true",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "linkedin_search_enabled")
    op.drop_column("users", "company_search_enabled")
    op.drop_column("users", "auto_apply_threshold")
    op.drop_table("company_scraping_logs")
    op.drop_table("target_companies")
    op.execute("DROP TYPE IF EXISTS scrapingerrortype")
    op.execute("DROP TYPE IF EXISTS scrapingrunstatus")
    op.execute("DROP TYPE IF EXISTS scrapestatus")
    op.execute("DROP TYPE IF EXISTS urldiscoverymethod")
