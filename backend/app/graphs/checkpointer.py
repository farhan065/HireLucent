"""Saves LangGraph state in PostgreSQL after every step.

This is what lets a graph pause for human approval, or survive a backend
restart, and continue later from where it stopped.
"""

from functools import lru_cache

from langgraph.checkpoint.postgres import PostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.core.config import get_settings


@lru_cache
def get_checkpointer() -> PostgresSaver:
    """Return the shared checkpointer, creating its connection pool once."""
    pool = ConnectionPool(
        conninfo=get_settings().postgres_dsn,
        max_size=10,
        # These three options are required by LangGraph's PostgreSQL saver.
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=True,
    )
    return PostgresSaver(pool)


def setup_checkpointer() -> None:
    """Create LangGraph's checkpoint tables if they do not exist yet."""
    get_checkpointer().setup()


def close_checkpointer() -> None:
    """Close the connection pool when the application stops."""
    get_checkpointer().conn.close()