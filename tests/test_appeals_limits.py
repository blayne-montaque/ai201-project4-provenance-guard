import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from provenance_guard import create_app
from provenance_guard.errors import APIError
from provenance_guard.groq_signal import unavailable
from provenance_guard.config import SCOUT_MODEL

SUBMIT = {"text": "Rain returns. The notebook waits. Another quiet morning.", "creator_id": "writer"}


def appeal_payload(content_id):
    return {"content_id": content_id, "creator_id": "writer",
            "creator_reasoning": "This is an intentional refrain from my own draft."}


def test_submission_to_appeal_and_persistent_history(app, client):
    original = client.post("/submit", json=SUBMIT).json
    payload = appeal_payload(original["content_id"])
    response = client.post("/appeal", json=payload)
    assert response.status_code == 201
    assert response.json["status"] == "under_review"
    for key in ("attribution", "confidence", "signals", "ai_likelihood_score", "label"):
        assert response.json[key] == original[key]
    restarted = create_app(dict(app.config)).test_client()
    record = restarted.get("/content/" + original["content_id"]).json
    assert record["status"] == "under_review" and record["appeal_filed"]
    events = restarted.get("/log").json["entries"]
    assert [e["event_type"] for e in events] == ["appeal", "submission"]
    assert events[0]["appeal_reasoning"] == payload["creator_reasoning"]
    assert events[1]["status"] == "classified" and not events[1]["appeal_filed"]
    assert client.post("/appeal", json=payload).status_code == 409
    assert len(client.get("/log").json["entries"]) == 2


def test_unknown_and_creator_mismatch(client):
    assert client.post("/appeal", json=appeal_payload("unknown")).status_code == 404
    record = client.post("/submit", json=SUBMIT).json
    assert client.post("/appeal", json=appeal_payload(record["content_id"]) |
                       {"creator_id": "impostor"}).status_code == 403
    assert client.get("/content/" + record["content_id"]).json["status"] == "classified"


@pytest.mark.parametrize("change", [{"creator_reasoning": ""}, {"creator_reasoning": "x" * 2001},
                                  {"creator_reasoning": 1}, {"content_id": []}, {"extra": "field"}])
def test_invalid_appeals(client, change):
    assert client.post("/appeal", json=appeal_payload("unknown") | change).status_code == 400


def test_appeal_rolls_back_if_audit_write_fails(app, client, monkeypatch):
    record = client.post("/submit", json=SUBMIT).json
    store = app.extensions["store"]

    def fail(*args):
        raise sqlite3.OperationalError("sensitive database detail")

    monkeypatch.setattr(store, "_event", fail)
    response = client.post("/appeal", json=appeal_payload(record["content_id"]))
    assert response.status_code == 503 and "sensitive" not in response.get_data(as_text=True)
    assert store.get(record["content_id"])["status"] == "classified"
    with store.connection() as db:
        assert db.execute("SELECT COUNT(*) FROM appeals").fetchone()[0] == 0
    assert len(store.log()) == 1


def test_concurrent_appeals_have_one_winner(app, client):
    record = client.post("/submit", json=SUBMIT).json
    store = app.extensions["store"]

    def attempt(_):
        try:
            store.appeal(record["content_id"], "writer", "Please review my draft.")
            return 201
        except APIError as exc:
            return exc.status

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(attempt, range(2))) == [201, 409]
    assert len(store.log()) == 2


def test_default_limits_and_headers(tmp_path):
    app = create_app({"TESTING": True, "DATABASE": tmp_path / "limits.sqlite3",
                      "RATELIMIT_ENABLED": True, "SUBMISSION_LIMITS": "10 per minute;100 per day",
                      "SEMANTIC_ANALYZER": lambda text: unavailable("offline_test", SCOUT_MODEL)})
    with app.test_client() as client:
        responses = [client.post("/submit", json=SUBMIT) for _ in range(12)]
        assert [response.status_code for response in responses] == [201] * 10 + [429, 429]
        assert responses[-1].json["error"]["code"] == "rate_limit_exceeded"
        assert int(responses[-1].headers["Retry-After"]) >= 0
        assert len(client.get("/log").json["entries"]) == 10
        assert client.post("/submit", json=SUBMIT,
                           environ_overrides={"REMOTE_ADDR": "127.0.0.2"}).status_code == 201


def test_daily_limit_is_applied_and_invalid_requests_count(app):
    config = dict(app.config) | {"RATELIMIT_ENABLED": True, "SUBMISSION_LIMITS": "100 per minute;2 per day"}
    client = create_app(config).test_client()
    assert client.post("/submit", json={}).status_code == 400
    assert client.post("/submit", json=SUBMIT).status_code == 201
    assert client.post("/submit", json=SUBMIT).status_code == 429


def test_invalid_unicode_is_rejected(client):
    assert client.post("/submit", json=SUBMIT | {"text": "\ud800"}).status_code == 400
