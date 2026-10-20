import statistics
import unicodedata

from .signals import Signal
from .text_metrics import sentences, words


def assess_stylometry(text):
    tokens = words(text)
    lengths = [len(words(sentence)) for sentence in sentences(text)]
    cv = statistics.pstdev(lengths) / statistics.mean(lengths) if lengths else 0.0
    ttr = len(set(tokens)) / len(tokens) if tokens else 0.0
    punctuation_kinds = len({char for char in text if unicodedata.category(char).startswith("P")})
    uniformity = 1 - min(cv, 1)
    lexical_concentration = 1 - ttr
    punctuation_uniformity = 1 - min(punctuation_kinds / 6, 1)
    score = 0.5 * uniformity + 0.3 * lexical_concentration + 0.2 * punctuation_uniformity
    return Signal("stylometry", score, insufficient_evidence=len(tokens) < 20 or len(lengths) < 2,
                  diagnostics={"word_count": len(tokens), "sentence_count": len(lengths),
                               "sentence_length_cv": cv, "type_token_ratio": ttr,
                               "punctuation_kinds": punctuation_kinds,
                               "assumption": "Uniformity is weak evidence, not proof of authorship."})

