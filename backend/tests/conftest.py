"""Test setup. Tests run ONLY against a database whose name ends in `_test`, and wipe it between tests."""

import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND / ".env", encoding="utf-8-sig")

TEST_URL = os.getenv("TEST_DATABASE_URL", "")
if not TEST_URL:
    pytest.exit("Set TEST_DATABASE_URL in backend/.env (a database whose name ends with _test).", returncode=2)

from sqlalchemy.engine import make_url  # noqa: E402

if not (make_url(TEST_URL).database or "").endswith("_test"):
    pytest.exit("TEST_DATABASE_URL must point at a database whose name ends with '_test'.", returncode=2)

os.environ["DATABASE_URL"] = TEST_URL  # must happen BEFORE importing the app
os.environ["CLINIC_TIMEZONE"] = "Asia/Karachi"
os.environ["GROQ_API_KEY"] = "test-key"
os.environ["GROQ_MODEL"] = "test-model"

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402

from app.database import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.utils.rate_limit import chat_limiter  # noqa: E402
from tests import factories  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def migrated_database():
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    command.upgrade(cfg, "head")
    yield


@pytest.fixture(autouse=True)
def clean_database(migrated_database):
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE appointments, conversation_messages, conversation_sessions, patients, "
            "doctor_schedules, doctor_services, doctors, services, clinic_info RESTART IDENTITY CASCADE"))
    chat_limiter.reset()
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def clinic(db):
    return factories.create_clinic(db)


@pytest.fixture
def sid():
    return str(uuid.uuid4())
