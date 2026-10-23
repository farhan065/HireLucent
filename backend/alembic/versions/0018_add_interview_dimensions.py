"""add interview dimensions

Revision ID: 0018
Revises: 0017
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'assessments',
        sa.Column('interview_dimensions', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('assessments', 'interview_dimensions')
