"""Alembic environment: connects migrations to the app settings and models."""

from alembic import context
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.models import Base

# Use the app's JSON logging so migration messages appear in the logs.
configure_logging(get_settings())

target_metadata = Base.metadata


def run_migrations() -> None:
    """Apply migrations using the database URL from the app settings."""
    engine = create_engine(get_settings().database_url)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()