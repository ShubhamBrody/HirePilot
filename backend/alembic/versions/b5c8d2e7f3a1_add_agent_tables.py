"""add agent tables

Revision ID: b5c8d2e7f3a1
Revises: a87f2aeb629d
Create Date: 2025-01-01 00:00:00.000000

"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = 'b5c8d2e7f3a1'
down_revision: Union[str, None] = 'a87f2aeb629d'
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    # email_tracking table
    op.create_table(
        'email_tracking',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('application_id', UUID(as_uuid=True), nullable=True, index=True),
        sa.Column('email_subject', sa.String(500), nullable=False),
        sa.Column('email_from', sa.String(255), nullable=False),
        sa.Column('email_date', sa.DateTime(timezone=True), nullable=False),
        sa.Column('classification', sa.String(50), nullable=False, index=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('company', sa.String(255), nullable=True),
        sa.Column('role', sa.String(255), nullable=True),
        sa.Column('next_action', sa.Text(), nullable=True),
        sa.Column('raw_snippet', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )

    # agent_executions table
    op.create_table(
        'agent_executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('agent_name', sa.String(100), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False, index=True),
        sa.Column('params', sa.Text(), nullable=True),
        sa.Column('result', sa.Text(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('items_processed', sa.Integer(), server_default='0'),
        sa.Column('duration_seconds', sa.Float(), server_default='0.0'),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
    )

    # New column on job_listings
    op.add_column(
        'job_listings',
        sa.Column('estimated_salary_breakdown', sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('job_listings', 'estimated_salary_breakdown')
    op.drop_table('agent_executions')
    op.drop_table('email_tracking')
