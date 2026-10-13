"""add suggested questions

Revision ID: 0013
Revises: 0012
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'interview_sessions',
        sa.Column('suggested_questions', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('interview_sessions', 'suggested_questions')
