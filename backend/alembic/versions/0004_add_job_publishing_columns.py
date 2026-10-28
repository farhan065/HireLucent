"""add job publishing columns

Revision ID: 0004
Revises: 0003
"""

from alembic import op
import sqlalchemy as sa


revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('jobs', sa.Column('form_id', sa.String(length=100), nullable=True))
    op.add_column('jobs', sa.Column('form_url', sa.String(length=500), nullable=True))
    op.add_column('jobs', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'published_at')
    op.drop_column('jobs', 'form_url')
    op.drop_column('jobs', 'form_id')
