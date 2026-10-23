"""Backend test fixtures.

Tests run against a throw-away copy of the local SQLite catalogue so search
logging and any future writes never touch the real file. Settings are read at
import time, so the environment is prepared before `app` is imported.
"""

import os
import shutil
import tempfile
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
_source = BACKEND_DIR / "catalogue.db"
_tmp = Path(tempfile.mkdtemp(prefix="catalogue-test-"))
_db = _tmp / "catalogue.db"
if _source.exists():
    shutil.copy(_source, _db)

os.environ.setdefault("HF_HUB_OFFLINE", "1")  # model is cached; a network probe can hang startup
os.environ["USE_LOCAL_DB"] = "true"
os.environ["ADMIN_TOKEN"] = "test-admin-token"  # mounts the admin routes under test
os.environ["LOCAL_DB_PATH"] = _db.as_posix()  # absolute path wins over BACKEND_DIR


@pytest.fixture(scope="session")
def client():
    if not _source.exists():
        pytest.skip("backend/catalogue.db not present (it is gitignored)")
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as c:  # runs lifespan, loads the embedding model once
        yield c


@pytest.fixture(scope="session")
def db_path():
    return _db
