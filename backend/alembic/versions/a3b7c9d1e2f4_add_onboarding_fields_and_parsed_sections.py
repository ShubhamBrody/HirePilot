"""add_onboarding_fields_and_parsed_sections

Revision ID: a3b7c9d1e2f4
Revises: fed9a23be6a2
Create Date: 2026-03-11 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b7c9d1e2f4'
down_revision: Union[str, None] = 'fed9a23be6a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User onboarding fields
    op.add_column('users', sa.Column('target_roles', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('preferred_technologies', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('preferred_companies', sa.Text(), nullable=True))
    op.add_column('users', sa.Column('experience_level', sa.String(length=50), nullable=True))
    op.add_column('users', sa.Column('email_for_outreach', sa.String(length=255), nullable=True))

    # Resume parsed sections
    op.add_column('resume_versions', sa.Column('parsed_sections', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('resume_versions', 'parsed_sections')
    op.drop_column('users', 'email_for_outreach')
    op.drop_column('users', 'experience_level')
    op.drop_column('users', 'preferred_companies')
    op.drop_column('users', 'preferred_technologies')
    op.drop_column('users', 'target_roles')
