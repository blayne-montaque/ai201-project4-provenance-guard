import pytest

from provenance_guard.stylometry import assess_stylometry

EXAMPLES = {
    "formal": "The relationship between monetary policy and asset price inflation has been extensively studied in the literature. Central banks face a fundamental tension between their mandate for price stability and the unintended consequences of prolonged low interest rates on equity and real estate valuations.",
    "casual": "ok so i finally tried that new ramen place downtown and honestly? underwhelming. the broth was fine but they put WAY too much sodium in it and i was thirsty for like three hours after. my friend got the spicy version and said it was better. probably won't go back unless someone drags me there",
    "poem": "Rain again.\nRain again.\nThe tin roof remembers.",
    "borderline": "I've been thinking a lot about remote work lately. There are genuine tradeoffs — flexibility and no commute on one side, isolation and blurred work-life boundaries on the other. Studies show productivity varies widely by individual and role type.",
    "polished": "Artificial intelligence represents a transformative paradigm shift in modern society. It is important to note that while the benefits of AI are numerous, it is equally essential to consider the ethical implications. Furthermore, stakeholders across various sectors must collaborate to ensure responsible deployment.",
}


@pytest.mark.parametrize("text", list(EXAMPLES.values()) + ["", "!!!", "你好世界。", "word"])
def test_stylometry_standalone_bounded(text):
    result = assess_stylometry(text)
    assert 0 <= result.score <= 1
    assert result == assess_stylometry(text)


def test_statistics_are_measured_and_samples_vary():
    regular = assess_stylometry("one two three. four five six. seven eight nine.")
    assert regular.diagnostics["sentence_length_cv"] == 0
    assert regular.diagnostics["type_token_ratio"] == 1
    assert regular.score == pytest.approx(0.5 + 0.2 * 5 / 6)
    assert assess_stylometry(EXAMPLES["poem"]).insufficient_evidence
    scores = {name: assess_stylometry(text).score for name, text in EXAMPLES.items()}
    assert abs(scores["formal"] - scores["casual"]) > 0.1
