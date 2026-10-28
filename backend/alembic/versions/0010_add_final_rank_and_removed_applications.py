"""add final rank and removed applications

Revision ID: 0010
Revises: 0009
"""

from alembic import op
import sqlalchemy as sa


revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('screening_results', sa.Column('final_rank', sa.Integer(), nullable=True))

    # Candidates scored before this step get their rank by final score.
    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT r.id, c.job_id, c.full_name, r.final_score, r.criteria_score "
        "FROM screening_results r JOIN candidates c ON c.id = r.candidate_id "
        "WHERE r.final_score IS NOT NULL AND r.excluded_reason IS NULL"
    )).fetchall()
    by_job: dict[int, list] = {}
    for result_id, job_id, name, final, criteria in rows:
        by_job.setdefault(job_id, []).append((result_id, final, criteria or 0, name))
    for results in by_job.values():
        results.sort(key=lambda item: (-item[1], -item[2], item[3].lower()))
        for rank, (result_id, _, _, _) in enumerate(results, start=1):
            connection.execute(
                sa.text("UPDATE screening_results SET final_rank = :r WHERE id = :i"),
                {"r": rank, "i": result_id},
            )

    op.create_table(
        'removed_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('response_id', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['job_id'], ['jobs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('job_id', 'response_id'),
    )
    op.create_index(op.f('ix_removed_applications_job_id'), 'removed_applications', ['job_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_removed_applications_job_id'), table_name='removed_applications')
    op.drop_table('removed_applications')
    op.drop_column('screening_results', 'final_rank')
