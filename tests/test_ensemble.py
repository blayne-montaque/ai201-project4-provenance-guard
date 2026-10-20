import pytest

from provenance_guard import create_app
from provenance_guard.ensemble import combine
from provenance_guard.labels import LABELS
from provenance_guard.repetition import assess_repetition
from provenance_guard.signals import Signal

LONG_TEXT = ("The writer placed her notebook on the table and thought about the strange sounds "
             "that had filled the old house while everyone else was sleeping. ") * 4


def signals(g, s, r, **kwargs):
    return {"groq": Signal("groq", g, **kwargs), "stylometry": Signal("stylometry", s),
            "repetition": Signal("repetition", r)}


def test_weighted_math_and_confidence():
    result = combine(LONG_TEXT, signals(.9, .8, .7))
    assert result["ai_likelihood_score"] == pytest.approx(.83)
    assert result["signal_agreement"] == pytest.approx(.8)
    assert result["confidence"] == pytest.approx(1 - .8 * .66)
    assert result["attribution"] == "uncertain"


@pytest.mark.parametrize("score,expected", [(0, "likely_human"), (.15, "likely_human"),
    (.150001, "uncertain"), (.5, "uncertain"), (.849999, "uncertain"), (.85, "likely_ai"), (1, "likely_ai")])
def test_exact_boundaries(score, expected):
    result = combine(LONG_TEXT, signals(score, score, score))
    assert result["attribution"] == expected
    assert result["label"] == LABELS[expected]
    assert result["confidence"] == pytest.approx(abs(2 * score - 1) if expected != "uncertain"
                                                else 1 - abs(2 * score - 1))


def test_disagreement_blocks_even_extreme_weighted_score():
    result = combine(LONG_TEXT, signals(1, 1, .25))
    assert result["ai_likelihood_score"] == .85
    assert result["attribution"] == "uncertain"
    assert "signal_disagreement" in result["uncertainty_reasons"]


def test_exact_disagreement_boundary_is_allowed():
    assert combine(LONG_TEXT, signals(1, 1, .5))["attribution"] == "likely_ai"


@pytest.mark.parametrize("kwargs", [{"insufficient_evidence": True}, {"diagnostics": {"uncertainty": True}}])
def test_semantic_flags_block_directional_result(kwargs):
    assert combine(LONG_TEXT, signals(.99, .99, .99, **kwargs))["attribution"] == "uncertain"


def test_short_text_and_nonalphabetic_evidence():
    result = combine("Rain. Again.", signals(1, 1, 1))
    assert result["attribution"] == "uncertain"
    assert result["evidence"]["sufficiency"] < 1
    assert "insufficient_text" in result["uncertainty_reasons"]
    result = combine(LONG_TEXT + "1234567890" * 500, signals(1, 1, 1))
    assert "low_alphabetic_content" in result["uncertainty_reasons"]


def test_missing_groq_never_looks_human():
    result = combine(LONG_TEXT, signals(None, .1, .1, available=False))
    assert result["ai_likelihood_score"] is None and result["confidence"] == 0
    assert result["attribution"] == "uncertain" and result["analysis_status"] == "degraded"


@pytest.mark.parametrize("invalid", [float("nan"), -1, 2, True, "0.5"])
def test_invalid_internal_signal_contract(invalid):
    with pytest.raises(ValueError):
        combine(LONG_TEXT, signals(invalid, .5, .5))


def test_lexical_signal_independent_metrics():
    repeated = assess_repetition("We remember the rain. " * 20)
    varied = assess_repetition("Mary found her notebook. The sleepy cat woke up. Nobody answered the telephone.")
    assert repeated.score > .8 and varied.score == 0
    assert not {"type_token_ratio", "sentence_length_cv"} & repeated.diagnostics.keys()
    assert assess_repetition("word").insufficient_evidence


@pytest.mark.parametrize("score,attribution", [(.95, "likely_ai"), (.05, "likely_human"), (.5, "uncertain")])
def test_all_labels_reachable_through_endpoint_with_controlled_signals(tmp_path, score, attribution):
    app = create_app({"TESTING": True, "DATABASE": tmp_path / "labels.sqlite3",
                      "RATELIMIT_ENABLED": False,
                      "SEMANTIC_ANALYZER": lambda text: Signal("groq", score),
                      "STYLOMETRIC_ANALYZER": lambda text: Signal("stylometry", score),
                      "REPETITION_ANALYZER": lambda text: Signal("repetition", score)})
    result = app.test_client().post("/submit", json={"text": LONG_TEXT, "creator_id": "test"})
    assert result.status_code == 201 and result.json["attribution"] == attribution
    assert result.json["label"] == LABELS[attribution]
