"""add candidate identification (F7)

Revision ID: 0015
Revises: 0014
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = '0015'
down_revision = '0014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('photo_path', sa.String(length=500), nullable=True))
    op.add_column('candidates', sa.Column('face_code', sa.LargeBinary(), nullable=True))
    op.add_column('candidates', sa.Column('face_status', sa.String(length=30), nullable=True))
    op.add_column('candidates', sa.Column('face_problem', sa.String(length=30), nullable=True))
    op.add_column(
        'candidates',
        sa.Column('face_consent_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'interview_sessions', sa.Column('pin_hash', sa.String(length=255), nullable=True)
    )
    op.add_column(
        'interview_sessions',
        sa.Column('pin_failed_attempts', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'interview_sessions',
        sa.Column('pin_locked_until', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'interview_sessions',
        sa.Column('identity_check', postgresql.JSONB(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('interview_sessions', 'identity_check')
    op.drop_column('interview_sessions', 'pin_locked_until')
    op.drop_column('interview_sessions', 'pin_failed_attempts')
    op.drop_column('interview_sessions', 'pin_hash')
    op.drop_column('candidates', 'face_consent_at')
    op.drop_column('candidates', 'face_problem')
    op.drop_column('candidates', 'face_status')
    op.drop_column('candidates', 'face_code')
    op.drop_column('candidates', 'photo_path')
