from collections.abc import Generator
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from food_order_bot.settings import Settings


def _ensure_sqlite_parent(database_url: str) -> None:
    if not database_url.startswith("sqlite:///"):
        return
    raw_path = database_url.removeprefix("sqlite:///")
    if raw_path == ":memory:":
        return
    Path(raw_path).parent.mkdir(parents=True, exist_ok=True)


def create_db_engine(settings: Settings):
    _ensure_sqlite_parent(settings.database_url)
    connect_args = (
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(settings.database_url, connect_args=connect_args)


def init_db(engine) -> None:
    SQLModel.metadata.create_all(engine)


def session_scope(engine) -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
