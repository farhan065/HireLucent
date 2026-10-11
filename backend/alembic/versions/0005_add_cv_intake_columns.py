"""add cv intake columns

Revision ID: 0005
Revises: 0004
"""

from alembic import op
import sqlalchemy as sa


revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('source_ref', sa.String(length=100), nullable=True))
    op.add_column('jobs', sa.Column('responses_seen', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('jobs', 'responses_seen')
    op.drop_column('candidates', 'source_ref')
