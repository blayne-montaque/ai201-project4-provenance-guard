import copy
import json

import pytest

from provenance_guard import create_app
from provenance_guard.labels import LABELS

METADATA = {"title": "Evening study", "medium": "image", "tools": ["Pencil", "Scanner"],
            "ai_disclosure": "none", "creation_steps": [
                {"description": "Sketched trees by the river.", "timestamp": "2026-01-01T13:00:00Z"},
                {"description": "Scanned the pencil drawing.", "timestamp": "2026-01-01T14:00:00Z"}]}


def submission(metadata=None):
    return {"creator_id": "artist", "content_type": "metadata",
            "metadata": METADATA if metadata is None else metadata}


def test_metadata_has_separate_path_and_can_be_appealed(app):
    def fail_if_called(text):
        raise AssertionError("Metadata must not call Groq")

    app = create_app(dict(app.config) | {"SEMANTIC_ANALYZER": fail_if_called})
    client = app.test_client()
    response = client.post("/submit", json=submission())
    assert response.status_code == 201
    record = response.json
    assert record["content_type"] == "metadata" and record["analysis_status"] == "metadata_only"
    assert record["ai_likelihood_score"] is None and record["confidence"] == 0
    assert record["label"] == LABELS["uncertain"]
    diagnostics = record["signals"]["metadata_consistency"]["diagnostics"]
    assert diagnostics["warnings"] == [] and diagnostics["step_count"] == 2
    appeal = client.post("/appeal", json={"creator_id": "artist", "content_id": record["content_id"],
                                          "creator_reasoning": "Please review the original drawing."})
    assert appeal.status_code == 201
    assert client.get("/analytics").json["content_types"] == {"metadata": 1}
    assert METADATA["creation_steps"][0]["description"] not in json.dumps(client.get("/log").json)


@pytest.mark.parametrize("change", [{"title": ""}, {"medium": "text"}, {"tools": "pencil"},
    {"tools": ["x"] * 21}, {"creation_steps": []}, {"creation_steps": ["not an object"]},
    {"creation_steps": [{"description": "x", "timestamp": "2026-01-01"}]},
    {"creation_steps": [{"description": "x", "timestamp": "bad"}]},
    {"ai_disclosure": "definitely_human"}, {"extra": 1}])
def test_invalid_metadata(client, change):
    assert client.post("/submit", json=submission(METADATA | change)).status_code == 400


def test_metadata_warnings_are_explicit(client):
    data = copy.deepcopy(METADATA)
    data["creation_steps"][0]["timestamp"] = "2099-01-01T00:00:00Z"
    data["creation_steps"][1]["description"] = data["creation_steps"][0]["description"]
    result = client.post("/submit", json=submission(data)).json
    warnings = result["signals"]["metadata_consistency"]["diagnostics"]["warnings"]
    assert set(warnings) == {"future_step_timestamp", "steps_out_of_order", "duplicate_step_descriptions"}


def test_text_and_metadata_share_submission_quota(app):
    client = create_app(dict(app.config) | {"RATELIMIT_ENABLED": True,
                                          "SUBMISSION_LIMITS": "2 per minute;100 per day"}).test_client()
    assert client.post("/submit", json=submission()).status_code == 201
    assert client.post("/submit", json={"creator_id": "artist", "text": "A poem."}).status_code == 201
    assert client.post("/submit", json=submission()).status_code == 429


def test_mixed_modality_payload_is_rejected(client):
    assert client.post("/submit", json=submission() | {"text": "Also text"}).status_code == 400
