import pytest


def test_empty_analytics_and_dashboard(client):
    metrics = client.get("/analytics").json
    assert metrics["total_submissions"] == 0
    assert metrics["appeal_rate"] == metrics["average_confidence"] == metrics["uncertainty_rate"] == 0
    page = client.get("/dashboard")
    assert page.status_code == 200 and "No submissions yet" in page.get_data(as_text=True)


def test_metrics_use_content_not_audit_event_denominator(app, client):
    store = app.extensions["store"]
    first = store.submit("writer", "work 1", {"attribution": "likely_ai", "confidence": .8})
    store.submit("writer", "work 2", {"attribution": "likely_human", "confidence": .7})
    store.submit("writer", "work 3", {"attribution": "uncertain", "confidence": .3,
                                      "uncertainty_reasons": ["signal_disagreement"]})
    store.appeal(first["content_id"], "writer", "Please review.")
    metrics = client.get("/analytics").json
    assert metrics["total_submissions"] == 3 and metrics["appeals_count"] == 1
    assert metrics["attribution_distribution"] == {"likely_ai": 1, "likely_human": 1, "uncertain": 1}
    assert metrics["appeal_rate"] == metrics["uncertainty_rate"] == metrics["signal_disagreement_rate"] == 1 / 3
    assert metrics["average_confidence"] == pytest.approx(.6)
    assert metrics["content_types"] == {"text": 3}
    html = client.get("/dashboard").get_data(as_text=True)
    assert "33.3%" in html and "0.600" in html
