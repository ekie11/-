import pytest
from fastapi.testclient import TestClient

from gostdoc_api.app import create_app
from gostdoc_api.config import get_settings
from gostdoc_api.models import Base


@pytest.fixture
def settings(tmp_path, monkeypatch):
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'test.db'}")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("STORAGE_DIR", str(storage))
    monkeypatch.setenv("COOKIE_SECURE", "false")
    get_settings.cache_clear()
    yield get_settings()
    get_settings.cache_clear()


@pytest.fixture
def app(settings):
    app = create_app(settings)
    Base.metadata.create_all(app.state.engine)
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db_session(app):
    session = app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()
