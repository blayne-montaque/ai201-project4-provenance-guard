import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from provenance_guard import create_app
from provenance_guard.config import SCOUT_MODEL
from provenance_guard.errors import APIError
from provenance_guard.groq_signal import assess_semantic, validate_assessment
from provenance_guard.signals import Signal


def test_missing_credentials_persist_actual_degraded_result(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": tmp_path / "offline.sqlite3", "GROQ_API_KEY": "",
                      "GROQ_MODEL": SCOUT_MODEL, "RATELIMIT_ENABLED": False})
    client = app.test_client()
    response = client.post("/submit", json={"creator_id": "offline", "text": "My poem. The rain. Again."})
    assert response.status_code == 201
    record = response.json
    assert record["analysis_status"] == "degraded" and record["ai_likelihood_score"] is None
    assert record["confidence"] == 0 and record["attribution"] == "uncertain"
    assert record["signals"]["groq"]["diagnostics"]["reason"] == "missing_api_key"
    assert client.get("/log").json["entries"][0]["signals"] == record["signals"]


def test_groq_constructor_has_bounded_timeout_no_retries(monkeypatch):
    observed = {}

    class FakeGroq:
        def __init__(self, **kwargs):
            observed.update(kwargs)
            self.chat = self
            self.completions = self

        def create(self, **kwargs):
            raise ValueError("Invalid service data")

        def close(self):
            observed["closed"] = True

    monkeypatch.setattr("provenance_guard.groq_signal.Groq", FakeGroq)
    result = assess_semantic("sample", {"GROQ_MODEL": SCOUT_MODEL, "GROQ_API_KEY": "local-test-only",
                                        "GROQ_TIMEOUT_SECONDS": 7})
    assert not result.available
    assert observed["timeout"] == 7 and observed["max_retries"] == 0 and observed["closed"]


def test_duplicate_valid_schema_key_is_rejected():
    raw = ('{"ai_likelihood":0.1,"ai_likelihood":0.9,"explanation":"Transitions.",'
           '"insufficient_evidence":false,"uncertainty":false}')
    assert not validate_assessment(raw, SCOUT_MODEL).available


def test_submission_rolls_back_when_audit_cannot_be_written(app, client, monkeypatch):
    store = app.extensions["store"]

    def fail(*args):
        import sqlite3
        raise sqlite3.OperationalError("private")

    monkeypatch.setattr(store, "_event", fail)
    assert client.post("/submit", json={"text": "A poem.", "creator_id": "writer"}).status_code == 503
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM contents").fetchone()[0] == 0


def test_simultaneous_verification_cannot_replay(app):
    service = app.extensions["verification"]
    registration = service.register("writer")
    challenge = service.challenge("writer")

    def attempt(_):
        try:
            service.verify("writer", challenge["challenge_id"], challenge["nonce"],
                           registration["verification_token"])
            return 201
        except APIError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 409]
    assert len(app.extensions["store"].log()) == 1


@pytest.mark.parametrize("route", ["/submit", "/appeal", "/creators/register", "/verification/challenge",
                                  "/verification/verify"])
def test_all_mutation_routes_reject_nonobject_json(client, route):
    response = client.post(route, data="[]", content_type="application/json")
    assert response.status_code == 400 and response.is_json


def test_certificate_rate_limit_enabled(app):
    client = create_app(dict(app.config) | {"RATELIMIT_ENABLED": True}).test_client()
    responses = [client.post("/creators/register", json={"creator_id": "writer"}) for _ in range(6)]
    assert [response.status_code for response in responses] == [201, 409, 409, 409, 409, 429]


def test_sql_injection_string_is_data(client):
    response = client.post("/appeal", json={"content_id": "'; DROP TABLE contents; --",
        "creator_id": "writer", "creator_reasoning": "Please review."})
    assert response.status_code == 404
    assert client.post("/submit", json={"creator_id": "writer", "text": "Still here."}).status_code == 201
