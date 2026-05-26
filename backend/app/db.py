import time
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.config import get_settings

engine = create_engine(get_settings().database_url, pool_pre_ping=True)


def create_db_and_tables(retries: int = 20, delay_seconds: float = 1.5) -> None:
    last_error: Exception | None = None
    for _ in range(retries):
        try:
            SQLModel.metadata.create_all(engine)
            return
        except Exception as exc:
            last_error = exc
            time.sleep(delay_seconds)
    if last_error:
        raise last_error


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
