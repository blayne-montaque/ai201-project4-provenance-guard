"""The fixed planning.md formula; no learned weights or empirical calibration."""
import math
from decimal import Decimal

from .labels import label_for
from .text_metrics import evidence

WEIGHTS = {"groq": 0.5, "stylometry": 0.3, "repetition": 0.2}


def combine(text, signals):
    if set(signals) != set(WEIGHTS):
        raise ValueError("Exactly the three planned signals are required")
    for name, signal in signals.items():
        if signal.name != name or (signal.available and (
            type(signal.score) not in (int, float) or not math.isfinite(signal.score)
            or not 0 <= signal.score <= 1
        )):
            raise ValueError("Invalid signal contract")
    info = evidence(text)
    reasons = []
    if info["word_count"] < 80 or info["sentence_count"] < 3:
        reasons.append("insufficient_text")
    if info["alphabetic_ratio"] < 0.5:
        reasons.append("low_alphabetic_content")
    for name, signal in signals.items():
        if not signal.available:
            reasons.append(f"{name}_unavailable")
        elif signal.insufficient_evidence:
            reasons.append(f"{name}_insufficient_evidence")
    if signals["groq"].diagnostics.get("uncertainty"):
        reasons.append("semantic_uncertainty")
    score, spread, agreement, confidence = None, None, None, 0.0
    attribution = "uncertain"
    if all(signal.available for signal in signals.values()):
        # Decimal avoids an inclusive boundary changing due to binary addition.
        values = [Decimal(str(signals[name].score)) for name in WEIGHTS]
        score = float(sum(Decimal(str(WEIGHTS[name])) * Decimal(str(signals[name].score))
                          for name in WEIGHTS))
        spread = float(max(values) - min(values))
        agreement = 1 - spread
        if spread > 0.5:
            reasons.append("signal_disagreement")
        if not reasons:
            if score >= 0.85:
                attribution = "likely_ai"
            elif score <= 0.15:
                attribution = "likely_human"
            else:
                reasons.append("intermediate_score")
        extremity = abs(2 * score - 1)
        confidence = info["sufficiency"] * (
            agreement * extremity if attribution != "uncertain" else 1 - agreement * extremity)
    return {"attribution": attribution, "ai_likelihood_score": score,
            "confidence": round(confidence, 6), "label": label_for(attribution),
            "score_interpretation": "uncalibrated AI-likelihood estimate; not proof of authorship",
            "signals": {name: signal.public() for name, signal in signals.items()},
            "weights": WEIGHTS.copy(), "evidence": info, "signal_spread": spread,
            "signal_agreement": agreement, "uncertainty_reasons": reasons,
            "analysis_status": "complete" if score is not None else "degraded"}

