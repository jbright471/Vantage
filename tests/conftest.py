import os
from pathlib import Path
import tempfile


TEST_DATABASE_PATH = Path(tempfile.gettempdir()) / "vantage-tests.sqlite3"
if TEST_DATABASE_PATH.exists():
    TEST_DATABASE_PATH.unlink()

os.environ.setdefault("VANTAGE_DATABASE_URL", f"sqlite+pysqlite:///{TEST_DATABASE_PATH.as_posix()}")
os.environ.setdefault("VANTAGE_ENABLE_BACKGROUND_POLLING", "0")
