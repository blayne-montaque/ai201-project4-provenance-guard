from .signals import Signal
from .text_metrics import sentences, words


def assess_repetition(text):
    tokens = words(text)
    trigrams = list(zip(tokens, tokens[1:], tokens[2:]))
    openings = [tuple(words(sentence)[:2]) for sentence in sentences(text)]
    trigram_reuse = 1 - len(set(trigrams)) / len(trigrams) if trigrams else 0.0
    opening_reuse = 1 - len(set(openings)) / len(openings) if openings else 0.0
    return Signal("repetition", 0.7 * trigram_reuse + 0.3 * opening_reuse,
                  insufficient_evidence=not trigrams or len(openings) < 2,
                  diagnostics={"trigram_count": len(trigrams), "unique_trigrams": len(set(trigrams)),
                               "repeated_trigram_fraction": trigram_reuse,
                               "repeated_opening_fraction": opening_reuse,
                               "assumption": "Literary refrains can resemble templated output."})

