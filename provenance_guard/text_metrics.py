"""Deterministic segmentation, not a language parser."""
import re


def words(text):
    return re.findall(r"[^\W\d_]+(?:['’][^\W\d_]+)*", text.lower(), flags=re.UNICODE)


def sentences(text):
    return [segment for segment in re.split(r"[.!?]+|\n+", text) if words(segment)]


def evidence(text):
    n, k = len(words(text)), len(sentences(text))
    visible = [char for char in text if not char.isspace()]
    alpha = sum(char.isalpha() for char in visible) / max(1, len(visible))
    return {"word_count": n, "sentence_count": k,
            "sufficiency": min(1, n / 80) * min(1, k / 3), "alphabetic_ratio": alpha}

