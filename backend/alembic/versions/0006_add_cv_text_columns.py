"""add cv text columns

Revision ID: 0006
Revises: 0005
"""

from alembic import op
import sqlalchemy as sa


revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('cv_text', sa.Text(), nullable=True))
    op.add_column('candidates', sa.Column('cv_text_source', sa.String(length=10), nullable=True))
    op.add_column('candidates', sa.Column('screening_error', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('candidates', 'screening_error')
    op.drop_column('candidates', 'cv_text_source')
    op.drop_column('candidates', 'cv_text')
