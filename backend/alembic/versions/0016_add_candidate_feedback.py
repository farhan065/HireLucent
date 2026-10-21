"""add candidate feedback emails (F11 innovation)

Revision ID: 0016
Revises: 0015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0016'
down_revision = '0015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'candidate_feedback',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column(
            'candidate_id',
            sa.Integer(),
            sa.ForeignKey('candidates.id', ondelete='CASCADE'),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            'job_id',
            sa.Integer(),
            sa.ForeignKey('jobs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        sa.Column('kind', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=30), nullable=False),
        sa.Column('written_by', sa.String(length=20), nullable=False),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('evidence', postgresql.JSONB(), nullable=False),
        sa.Column('warnings', postgresql.JSONB(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('error_message', sa.String(length=255), nullable=True),
        sa.Column('sent_anyway', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('approved_by', sa.Integer(), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
    )
    op.create_index('ix_candidate_feedback_job_id', 'candidate_feedback', ['job_id'])
    # A decision of "hold" was possible before; it is no longer used.
    op.execute("UPDATE candidates SET decision = NULL WHERE decision = 'hold'")


def downgrade() -> None:
    op.drop_index('ix_candidate_feedback_job_id', table_name='candidate_feedback')
    op.drop_table('candidate_feedback')
