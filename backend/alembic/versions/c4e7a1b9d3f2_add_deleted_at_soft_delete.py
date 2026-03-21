"""add_deleted_at_soft_delete

Revision ID: c4e7a1b9d3f2
Revises: 6159f7dbe8e8
Create Date: 2026-03-21 02:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e7a1b9d3f2'
down_revision: Union[str, None] = '6159f7dbe8e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'applications',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'job_listings',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'resume_versions',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'recruiters',
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_applications_deleted_at', 'applications', ['deleted_at'])
    op.create_index('ix_job_listings_deleted_at', 'job_listings', ['deleted_at'])
    op.create_index('ix_resume_versions_deleted_at', 'resume_versions', ['deleted_at'])
    op.create_index('ix_recruiters_deleted_at', 'recruiters', ['deleted_at'])


def downgrade() -> None:
    op.drop_index('ix_recruiters_deleted_at', table_name='recruiters')
    op.drop_index('ix_resume_versions_deleted_at', table_name='resume_versions')
    op.drop_index('ix_job_listings_deleted_at', table_name='job_listings')
    op.drop_index('ix_applications_deleted_at', table_name='applications')
    op.drop_column('recruiters', 'deleted_at')
    op.drop_column('resume_versions', 'deleted_at')
    op.drop_column('job_listings', 'deleted_at')
    op.drop_column('applications', 'deleted_at')
