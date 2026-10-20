"""Second modality: structured workflow metadata, not image/audio inspection."""
import json
from datetime import datetime, timezone

from .errors import APIError
from .labels import label_for
from .validation import fields, string


def analyze_metadata(value, now=None):
    if type(value) is not dict:
        raise APIError("invalid_metadata", "metadata must be an object.")
    fields(value, ("title", "medium", "tools", "creation_steps", "ai_disclosure"))
    title = string(value, "title", 200)
    medium = string(value, "medium", 20)
    if medium not in {"image", "audio", "video", "mixed_media"}:
        raise APIError("invalid_medium", "medium must be image, audio, video, or mixed_media.")
    disclosure = string(value, "ai_disclosure", 20)
    if disclosure not in {"none", "assisted", "generated", "undisclosed"}:
        raise APIError("invalid_disclosure", "Unsupported self-reported AI disclosure.")
    tool_values, step_values = value["tools"], value["creation_steps"]
    if type(tool_values) is not list or len(tool_values) > 20:
        raise APIError("invalid_tools", "tools must be a list containing at most 20 names.")
    tool_names = [string({"tool": tool}, "tool", 80) for tool in tool_values]
    if type(step_values) is not list or not 1 <= len(step_values) <= 20:
        raise APIError("invalid_steps", "creation_steps must contain 1 to 20 steps.")
    steps, timestamps = [], []
    for step in step_values:
        if type(step) is not dict:
            raise APIError("invalid_step", "Each creation step must be an object.")
        fields(step, ("description", "timestamp"))
        description, timestamp = string(step, "description", 500), string(step, "timestamp", 50)
        try:
            parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError()
            parsed = parsed.astimezone(timezone.utc)
        except (ValueError, OverflowError):
            raise APIError("invalid_timestamp", "Step timestamps must be timezone-aware ISO dates and times.") from None
        timestamps.append(parsed)
        steps.append({"description": description, "timestamp": parsed.isoformat()})
    now = now or datetime.now(timezone.utc)
    warnings = []
    if timestamps != sorted(timestamps):
        warnings.append("steps_out_of_order")
    if any(timestamp > now for timestamp in timestamps):
        warnings.append("future_step_timestamp")
    if len({step["description"].casefold() for step in steps}) < len(steps):
        warnings.append("duplicate_step_descriptions")
    canonical = json.dumps({"title": title, "medium": medium, "tools": tool_names,
                            "creation_steps": steps, "ai_disclosure": disclosure},
                           sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    assessment = {"attribution": "uncertain", "ai_likelihood_score": None, "confidence": 0.0,
                  "label": label_for("uncertain"), "analysis_status": "metadata_only",
                  "score_interpretation": "Metadata consistency cannot establish authorship.",
                  "uncertainty_reasons": ["metadata_is_self_reported", "underlying_media_not_analyzed"],
                  "signals": {"metadata_consistency": {"name": "metadata_consistency",
                      "score": None, "available": True, "insufficient_evidence": True,
                      "diagnostics": {"medium": medium, "step_count": len(steps),
                          "tool_count": len(tool_names), "self_reported_ai_disclosure": disclosure,
                          "warnings": warnings, "authorship_verified": False}}}}
    return canonical, assessment
