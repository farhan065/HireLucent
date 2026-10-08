"""add match ranking columns

Revision ID: 0008
Revises: 0007

Adds the match score and rank to screening results, and fills them in for
candidates that were matched before this step existed. The score formula
is the one in app.graphs.screening.matching.match_score, repeated here so
the migration keeps working if that code changes later.
"""

from alembic import op
import sqlalchemy as sa


revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None

POINTS = {"met": 1.0, "partially_met": 0.5, "unmet": 0.0}


def _score(matches: list[dict]) -> float:
    weights = [2 if item.get("priority") == "must_have" else 1 for item in matches]
    if not weights:
        return 0.0
    earned = sum(w * POINTS.get(item["status"], 0) for w, item in zip(weights, matches))
    return round(100 * earned / sum(weights), 1)


def upgrade() -> None:
    op.add_column('screening_results', sa.Column('match_score', sa.Float(), nullable=True))
    op.add_column('screening_results', sa.Column('rank', sa.Integer(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(sa.text(
        "SELECT r.id, c.job_id, c.full_name, r.requirement_matches "
        "FROM screening_results r JOIN candidates c ON c.id = r.candidate_id "
        "WHERE r.requirement_matches IS NOT NULL AND r.excluded_reason IS NULL"
    )).fetchall()
    by_job: dict[int, list] = {}
    for result_id, job_id, name, matches in rows:
        must_met = sum(
            1 for item in matches
            if item.get("priority") == "must_have" and item["status"] == "met"
        )
        by_job.setdefault(job_id, []).append((result_id, _score(matches), must_met, name))
    for results in by_job.values():
        results.sort(key=lambda item: (-item[1], -item[2], item[3].lower()))
        for rank, (result_id, score, _, _) in enumerate(results, start=1):
            connection.execute(
                sa.text("UPDATE screening_results SET match_score = :s, rank = :r WHERE id = :i"),
                {"s": score, "r": rank, "i": result_id},
            )


def downgrade() -> None:
    op.drop_column('screening_results', 'rank')
    op.drop_column('screening_results', 'match_score')
