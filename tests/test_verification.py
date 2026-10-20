import json

import pytest

from provenance_guard import create_app


def setup_challenge(client, creator="writer"):
    registration = client.post("/creators/register", json={"creator_id": creator})
    assert registration.status_code == 201
    challenge = client.post("/verification/challenge", json={"creator_id": creator})
    assert challenge.status_code == 201
    return {"creator_id": creator, "challenge_id": challenge.json["challenge_id"],
            "nonce": challenge.json["nonce"], "verification_token": registration.json["verification_token"]}


def test_certificate_requires_verification_and_displays_on_content(app, client):
    content = client.post("/submit", json={"creator_id": "writer", "text": "A creative draft."}).json
    assert content["certificate"] is None
    payload = setup_challenge(client)
    response = client.post("/verification/verify", json=payload)
    assert response.status_code == 201
    certificate = response.json
    assert certificate["verification_status"] == "verified_secret_control"
    assert "not humanity" in certificate["scope"]
    restarted = create_app(dict(app.config)).test_client()
    assert restarted.get("/certificates/" + certificate["certificate_id"]).json["valid"]
    assert restarted.get("/content/" + content["content_id"]).json["certificate"] == certificate
    again = client.post("/verification/verify", json=payload)
    assert again.status_code == 409
    assert client.post("/creators/register", json={"creator_id": "writer"}).status_code == 409
    assert client.get("/certificates/unknown").status_code == 404
    # Whole database file and all exported events must not contain token or nonce.
    database = open(app.config["DATABASE"], "rb").read()
    events = json.dumps(client.get("/log").json)
    for field in ("verification_token", "nonce"):
        assert payload[field].encode() not in database and payload[field] not in events


@pytest.mark.parametrize("change,status", [({"verification_token": "wrong"}, 403),
    ({"nonce": "wrong"}, 403), ({"creator_id": "other"}, 404), ({"challenge_id": "unknown"}, 404)])
def test_wrong_verification_never_issues(app, client, change, status):
    payload = setup_challenge(client)
    assert client.post("/verification/verify", json=payload | change).status_code == status
    assert app.extensions["verification"].for_creator("writer") is None


def test_expired_challenge(app, client):
    payload = setup_challenge(client)
    verification = app.extensions["verification"]
    now = verification.clock()
    verification.clock = lambda: now + 301
    assert client.post("/verification/verify", json=payload).status_code == 410


def test_attempts_persist_and_lock_challenge(client):
    payload = setup_challenge(client)
    for _ in range(5):
        assert client.post("/verification/verify", json=payload | {"nonce": "wrong"}).status_code == 403
    assert client.post("/verification/verify", json=payload).status_code == 429


def test_new_challenge_invalidates_previous_and_certificate_is_stable(client):
    payload = setup_challenge(client)
    challenge = client.post("/verification/challenge", json={"creator_id": "writer"}).json
    assert client.post("/verification/verify", json=payload).status_code == 409
    payload.update({key: challenge[key] for key in ("nonce", "challenge_id")})
    first = client.post("/verification/verify", json=payload).json
    challenge = client.post("/verification/challenge", json={"creator_id": "writer"}).json
    payload.update({key: challenge[key] for key in ("nonce", "challenge_id")})
    assert client.post("/verification/verify", json=payload).json == first
    assert len(client.get("/log").json["entries"]) == 1


def test_unregistered_and_malformed_verification(client):
    assert client.post("/verification/challenge", json={"creator_id": "nobody"}).status_code == 404
    assert client.post("/verification/verify", json={}).status_code == 400
