import pytest

from provenance_guard import create_app
from provenance_guard.signals import Signal


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.sqlite3"),
                       "GROQ_API_KEY": "", "RATELIMIT_ENABLED": False,
                       "SEMANTIC_ANALYZER": lambda text: Signal("groq", 0.5, diagnostics={"uncertainty": True})})


@pytest.fixture
def client(app):
    return app.test_client()

