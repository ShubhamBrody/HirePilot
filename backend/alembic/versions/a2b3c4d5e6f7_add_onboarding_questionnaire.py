"""add_onboarding_questionnaire

Revision ID: a2b3c4d5e6f7
Revises: b5c8d2e7f3a1
Create Date: 2026-03-19 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "b5c8d2e7f3a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Personal information
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("gender", sa.String(20), nullable=True))
    op.add_column("users", sa.Column("nationality", sa.String(100), nullable=True))
    op.add_column("users", sa.Column("address", sa.Text(), nullable=True))

    # Work history
    op.add_column("users", sa.Column("current_company", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("current_title", sa.String(255), nullable=True))
    op.add_column("users", sa.Column("years_of_experience", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("notice_period_days", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("work_authorization", sa.String(100), nullable=True))

    # Salary & compensation
    op.add_column("users", sa.Column("current_salary_base", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("current_salary_bonus", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("current_salary_rsu", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("current_salary_ctc", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("salary_currency", sa.String(10), nullable=True, server_default="USD"))
    op.add_column("users", sa.Column("expected_salary_min", sa.Float(), nullable=True))
    op.add_column("users", sa.Column("expected_salary_max", sa.Float(), nullable=True))

    # Education
    op.add_column("users", sa.Column("education", sa.Text(), nullable=True))

    # Job preferences
    op.add_column("users", sa.Column("willing_to_relocate", sa.Boolean(), nullable=True))
    op.add_column("users", sa.Column("remote_preference", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("job_type_preference", sa.String(50), nullable=True))

    # Classified skills
    op.add_column("users", sa.Column("classified_skills", sa.Text(), nullable=True))

    # EEO & misc
    op.add_column("users", sa.Column("cover_letter_default", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("disability_status", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("veteran_status", sa.String(50), nullable=True))

    # Onboarding tracking
    op.add_column("users", sa.Column("onboarding_completed", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("users", sa.Column("onboarding_step", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    op.drop_column("users", "onboarding_step")
    op.drop_column("users", "onboarding_completed")
    op.drop_column("users", "veteran_status")
    op.drop_column("users", "disability_status")
    op.drop_column("users", "cover_letter_default")
    op.drop_column("users", "classified_skills")
    op.drop_column("users", "job_type_preference")
    op.drop_column("users", "remote_preference")
    op.drop_column("users", "willing_to_relocate")
    op.drop_column("users", "education")
    op.drop_column("users", "expected_salary_max")
    op.drop_column("users", "expected_salary_min")
    op.drop_column("users", "salary_currency")
    op.drop_column("users", "current_salary_ctc")
    op.drop_column("users", "current_salary_rsu")
    op.drop_column("users", "current_salary_bonus")
    op.drop_column("users", "current_salary_base")
    op.drop_column("users", "work_authorization")
    op.drop_column("users", "notice_period_days")
    op.drop_column("users", "years_of_experience")
    op.drop_column("users", "current_title")
    op.drop_column("users", "current_company")
    op.drop_column("users", "address")
    op.drop_column("users", "nationality")
    op.drop_column("users", "gender")
    op.drop_column("users", "date_of_birth")
