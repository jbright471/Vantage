import os

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("VANTAGE_DATABASE_URL", "sqlite+pysqlite:///./vantage.sqlite3")

engine = create_engine(DATABASE_URL, future=True, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    table_names = inspector.get_table_names()
    if "routing_rules" in table_names:
        routing_columns = {column["name"] for column in inspector.get_columns("routing_rules")}
        with engine.begin() as connection:
            if "allow_degraded" not in routing_columns:
                connection.execute(text("ALTER TABLE routing_rules ADD COLUMN allow_degraded BOOLEAN NOT NULL DEFAULT 0"))
            if "allow_stale" not in routing_columns:
                connection.execute(text("ALTER TABLE routing_rules ADD COLUMN allow_stale BOOLEAN NOT NULL DEFAULT 0"))
            if "allow_unreachable" not in routing_columns:
                connection.execute(
                    text("ALTER TABLE routing_rules ADD COLUMN allow_unreachable BOOLEAN NOT NULL DEFAULT 0")
                )
            if "minimum_eval_pass_rate" not in routing_columns:
                connection.execute(text("ALTER TABLE routing_rules ADD COLUMN minimum_eval_pass_rate FLOAT"))

    if "eval_schedules" not in table_names:
        return

    columns = {column["name"] for column in inspector.get_columns("eval_schedules")}
    with engine.begin() as connection:
        if "auto_execute" not in columns:
            connection.execute(text("ALTER TABLE eval_schedules ADD COLUMN auto_execute BOOLEAN NOT NULL DEFAULT 0"))

    if "eval_cases" not in table_names:
        return

    case_columns = {column["name"] for column in inspector.get_columns("eval_cases")}
    with engine.begin() as connection:
        if "score_type" not in case_columns:
            connection.execute(
                text("ALTER TABLE eval_cases ADD COLUMN score_type VARCHAR NOT NULL DEFAULT 'json_subset'")
            )
        if "score_config_json" not in case_columns:
            connection.execute(text("ALTER TABLE eval_cases ADD COLUMN score_config_json JSON NOT NULL DEFAULT '{}'"))
