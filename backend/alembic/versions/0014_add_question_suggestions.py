"""add question suggestions

Revision ID: 0014
Revises: 0013
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0014'
down_revision = '0013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'assessments',
        sa.Column('question_suggestions', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('assessments', 'question_suggestions')
