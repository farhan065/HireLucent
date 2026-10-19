"""ScreeningService: runs the CV Screening graph for a job in the background."""

from fastapi import BackgroundTasks
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.errors import ConflictError
from app.core.logging import get_logger, log_event
from app.graphs.base import thread_config
from app.graphs.screening import store
from app.models import Task
from app.services import job_service, task_service
from app.services.task_service import TaskProgress

logger = get_logger(__name__)

TASK_KIND = "cv_screening"
NOTHING_TO_SCREEN = "There are no new CVs to screen. Fetch CVs first."


def start_screening(
    db: Session,
    background_tasks: BackgroundTasks,
    graph: CompiledStateGraph,
    job_id: int,
    user_id: int,
) -> Task:
    """Start screening a job's waiting CVs and return the task."""
    job_service.get_job(db, job_id)
    task_service.ensure_idle(db, job_id, exclude=(task_service.EVALUATION,))
    if not store.count_to_screen(job_id):
        raise ConflictError(NOTHING_TO_SCREEN)
    return task_service.start_task(
        db,
        background_tasks,
        TASK_KIND,
        user_id,
        lambda progress: run_screening(graph, job_id, progress),
        job_id=job_id,
    )


def thread_id(task_id: str) -> str:
    """Each run is its own thread, so its checkpoints do not mix with others."""
    return f"screening-{task_id}"


def run_screening(
    graph: CompiledStateGraph, job_id: int, progress: TaskProgress
) -> dict[str, int]:
    """Run the graph, reporting progress as each CV finishes."""
    total = store.count_to_screen(job_id)
    config = thread_config(thread_id(progress.task_id))
    config["max_concurrency"] = get_settings().screening_max_parallel

    done = 0
    progress.update(done, total, f"Screening {total} CVs")
    for update in graph.stream({"job_id": job_id}, config, stream_mode="updates"):
        if "screen_cv" in update:
            done += 1
            progress.update(done, total, f"Processed {done} of {total} CVs")

    summary = graph.get_state(config).values["summary"]
    log_event(logger, "cv_screening_finished", job_id=job_id, **summary)
    return summary
