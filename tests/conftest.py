import os
import tempfile
from pathlib import Path

import pytest

# Testlar alohida SQLite faylida ishlaydi (Postgres shart emas)
_tmp = Path(tempfile.mkdtemp()) / "test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}"
os.environ["SECRET_KEY"] = "test"
os.environ["MEDIA_DIR"] = str(_tmp.parent / "media")
os.environ["TELEGRAM_BOT_TOKEN"] = ""
os.environ["TELEGRAM_CHAT_ID"] = "777"
os.environ["TELEGRAM_WEBHOOK_SECRET"] = "hook-secret"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from scripts.seed import seed  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)
