import json
from types import SimpleNamespace

import httpx
import pytest
from groq import APIConnectionError, APIStatusError, APITimeoutError

from provenance_guard.config import ALTERNATE_MODEL, SCOUT_MODEL
from provenance_guard.groq_signal import assess_semantic, validate_assessment

VALID = {"ai_likelihood": 0.8, "explanation": "Uniform transitions.",
         "insufficient_evidence": False, "uncertainty": False}


class FakeClient:
    def __init__(self, result=None, error=None, finish="stop"):
        self.chat = SimpleNamespace(completions=self)
        self.result = json.dumps(VALID) if result is None else result
        self.error, self.finish, self.kwargs = error, finish, None

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(
            message=SimpleNamespace(content=self.result), finish_reason=self.finish)])


def test_semantic_independent():
    client = FakeClient()
    signal = assess_semantic("An independent signal sample.", {"GROQ_MODEL": SCOUT_MODEL}, client)
    assert signal.score == 0.8 and signal.available
    assert client.kwargs["response_format"] == {"type": "json_object"}
    assert client.kwargs["messages"][1]["role"] == "user"


@pytest.mark.parametrize("change", [
    {"ai_likelihood": True}, {"ai_likelihood": -0.1}, {"ai_likelihood": 1.1},
    {"ai_likelihood": "0.7"}, {"ai_likelihood": float("nan")},
    {"ai_likelihood": float("inf")}, {"explanation": ""}, {"explanation": "x" * 401},
    {"explanation": None}, {"uncertainty": "false"}, {"insufficient_evidence": 0},
    {"extra": "unwanted"},
])
def test_rejects_invalid_model_fields(change):
    signal = validate_assessment(json.dumps(VALID | change), SCOUT_MODEL)
    assert not signal.available and signal.score is None


@pytest.mark.parametrize("raw", ["not JSON", "[]", "null", "{}", '{"x":1,"x":2}', None])
def test_rejects_malformed_response(raw):
    assert not validate_assessment(raw, SCOUT_MODEL).available


def test_secret_cannot_escape_in_explanation():
    assert not validate_assessment(json.dumps(VALID | {"explanation": "test-private-value"}),
                                   SCOUT_MODEL, "test-private-value").available


@pytest.mark.parametrize("kind,reason", [("timeout", "timeout"), ("connect", "connection_error"),
                                         ("status", "model_not_found")])
def test_failures_are_sanitized(kind, reason):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    error = {"timeout": APITimeoutError(request=request),
             "connect": APIConnectionError(request=request),
             "status": APIStatusError("PRIVATE EXCEPTION", response=httpx.Response(404, request=request),
                                      body={"error": {"code": "model_not_found"}})}[kind]
    signal = assess_semantic("sample", {"GROQ_MODEL": SCOUT_MODEL}, FakeClient(error=error))
    assert signal.diagnostics["reason"] == reason
    assert "PRIVATE" not in json.dumps(signal.public())


def test_missing_key_and_no_unauthorized_fallback():
    assert assess_semantic("sample", {"GROQ_MODEL": SCOUT_MODEL}).diagnostics["reason"] == "missing_api_key"
    config = {"GROQ_MODEL": ALTERNATE_MODEL}
    assert assess_semantic("sample", config, FakeClient()).diagnostics["reason"] == "model_not_authorized"
    assert assess_semantic("sample", config | {"ALLOW_ALTERNATE_MODEL": True}, FakeClient()).available


def test_truncated_response_is_unavailable():
    signal = assess_semantic("sample", {"GROQ_MODEL": SCOUT_MODEL}, FakeClient(finish="length"))
    assert signal.diagnostics["reason"] == "incomplete_model_response"
