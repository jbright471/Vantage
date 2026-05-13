from backend.app.db import engine_options_for_url, is_sqlite_database_url


def test_sqlite_database_url_keeps_thread_override() -> None:
    database_url = "sqlite+pysqlite:///./vantage.sqlite3"

    assert is_sqlite_database_url(database_url)
    assert engine_options_for_url(database_url) == {"connect_args": {"check_same_thread": False}}


def test_postgres_database_url_uses_pool_pre_ping_without_sqlite_args() -> None:
    database_url = "postgresql+psycopg://vantage:secret@db.example.test:5432/vantage"

    assert not is_sqlite_database_url(database_url)
    assert engine_options_for_url(database_url) == {"pool_pre_ping": True}
