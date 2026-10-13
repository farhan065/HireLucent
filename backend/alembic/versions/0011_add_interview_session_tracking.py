"""add interview session tracking

Revision ID: 0011
Revises: 0010
"""

from alembic import op
import sqlalchemy as sa


revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('interview_sessions', sa.Column('created_by', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_interview_sessions_created_by_users',
        'interview_sessions',
        'users',
        ['created_by'],
        ['id'],
        ondelete='SET NULL',
    )
    op.add_column(
        'interview_sessions',
        sa.Column('interviewer_joined_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'interview_sessions',
        sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        op.f('ix_interview_sessions_job_id'), 'interview_sessions', ['job_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_interview_sessions_job_id'), table_name='interview_sessions')
    op.drop_column('interview_sessions', 'cancelled_at')
    op.drop_column('interview_sessions', 'interviewer_joined_at')
    op.drop_constraint(
        'fk_interview_sessions_created_by_users', 'interview_sessions', type_='foreignkey'
    )
    op.drop_column('interview_sessions', 'created_by')
