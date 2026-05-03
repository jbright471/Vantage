import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("VANTAGE_DATABASE_URL", "sqlite+pysqlite:///./vantage.sqlite3")

engine = create_engine(DATABASE_URL, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    if "eval_schedules" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("eval_schedules")}
    with engine.begin() as connection:
        if "auto_execute" not in columns:
            connection.execute(text("ALTER TABLE eval_schedules ADD COLUMN auto_execute BOOLEAN NOT NULL DEFAULT 0"))
