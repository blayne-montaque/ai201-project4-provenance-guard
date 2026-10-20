import json
from uuid import UUID

import pytest

from provenance_guard import create_app

PAYLOAD = {"text": "A small creative work about a misplaced notebook.", "creator_id": "creator-1"}


def test_startup_and_submit(client):
    assert client.get("/health").json["status"] == "ok"
    response = client.post("/submit", json=PAYLOAD)
    assert response.status_code == 201
    record = response.json
    assert str(UUID(record["content_id"])) == record["content_id"]
    assert record["status"] == "classified"
    assert 0 <= record["confidence"] <= 1
    assert client.get("/content/" + record["content_id"]).json == record
    event = client.get("/log").json["entries"][0]
    assert event["attribution"] == record["attribution"]
    assert event["event_type"] == "submission"
    assert PAYLOAD["text"] not in json.dumps(event)


@pytest.mark.parametrize("payload", [None, [], {}, {"text": "x"}, {"creator_id": "x"},
    PAYLOAD | {"text": " "}, PAYLOAD | {"text": 3}, PAYLOAD | {"text": "a" * 20001},
    PAYLOAD | {"creator_id": ""}, PAYLOAD | {"creator_id": "x" * 81},
    PAYLOAD | {"creator_id": "a b"}, PAYLOAD | {"extra": True},
    PAYLOAD | {"content_type": "image"}])
def test_invalid_inputs(client, payload):
    response = client.post("/submit", data=json.dumps(payload), content_type="application/json")
    assert response.status_code == 400
    assert set(response.json["error"]) == {"code", "message"}
    assert client.get("/log").json == {"entries": []}


@pytest.mark.parametrize("raw", ['{', '{"text":"a","text":"b","creator_id":"x"}',
                                 '{"text":NaN,"creator_id":"x"}'])
def test_malformed_json(client, raw):
    assert client.post("/submit", data=raw, content_type="application/json").status_code == 400


def test_content_type_and_body_limit(client):
    assert client.post("/submit", data="not-json").status_code == 400
    assert client.post("/submit", data="x" * (128 * 1024 + 1),
                       content_type="application/json").status_code == 413


@pytest.mark.parametrize("limit", ["0", "201", "bad", "1.5"])
def test_log_limit(client, limit):
    assert client.get("/log?limit=" + limit).status_code == 400


def test_unique_ids_and_restart_persistence(app, client):
    first = client.post("/submit", json=PAYLOAD).json
    second = client.post("/submit", json=PAYLOAD).json
    assert first["content_id"] != second["content_id"]
    restarted = create_app(dict(app.config)).test_client()
    assert restarted.get("/content/" + first["content_id"]).json == first
    assert len(restarted.get("/log").json["entries"]) == 2


def test_unknown_content(client):
    assert client.get("/content/unknown").status_code == 404
    assert client.get("/unknown").is_json
