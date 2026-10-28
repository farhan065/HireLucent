"""add task job column

Revision ID: 0007
Revises: 0006
"""

from alembic import op
import sqlalchemy as sa


revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('job_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ix_tasks_job_id'), 'tasks', ['job_id'], unique=False)
    op.create_foreign_key(
        'fk_tasks_job_id_jobs', 'tasks', 'jobs', ['job_id'], ['id'], ondelete='CASCADE'
    )


def downgrade() -> None:
    op.drop_constraint('fk_tasks_job_id_jobs', 'tasks', type_='foreignkey')
    op.drop_index(op.f('ix_tasks_job_id'), table_name='tasks')
    op.drop_column('tasks', 'job_id')
