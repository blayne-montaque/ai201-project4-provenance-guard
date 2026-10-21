# Authorized Groq model substitution

On October 20, 2026 (America/New_York), the project owner answered the pending
model-substitution question: **"Authorize openai/gpt-oss-20b"**.

The prescribed first attempt used `meta-llama/llama-4-scout-17b-16e-instruct` and
returned HTTP 404 `model_not_found`. The original sanitized evidence is preserved
in [groq_smoke_scout.json](groq_smoke_scout.json). The account's model list showed
Scout unavailable and `openai/gpt-oss-20b` available.

After that explicit approval, the existing private `.env` was configured with
`GROQ_MODEL=openai/gpt-oss-20b` and `ALLOW_ALTERNATE_MODEL=true`. The API key was
preserved, not displayed or committed. The application still defaults to Scout
in a fresh environment and never silently switches models after a failure.

The authorized model's independent smoke test succeeded at
`2026-10-21T00:03:47.346461+00:00` (October 20, 8:03 PM EDT). Its structured semantic
score was 0.3 with `uncertainty: true`; see
[groq_smoke_authorized.json](groq_smoke_authorized.json). This is a semantic signal
score, not the final ensemble confidence.

The subsequent [live endpoint run](demo_live/observations.json) submitted six
bundled public texts through the actual Flask handlers, called Groq for each one,
and stored the real decisions in SQLite. No signal was injected or mocked in this
run. Every live semantic response passed the strict schema validation. The run also
exercised an appeal, verification certificate, metadata submission and dashboard.

| Example | Raw AI-likelihood estimate | Decision confidence | Attribution |
|---|---:|---:|---|
| synthetic_template | 0.608906779661017 | 0.864150 | uncertain |
| synthetic_short_poem | 0.38946699141100893 | 0.088171 | uncertain |

These are real high/lower **decision-confidence** examples. The larger value
means support for reporting uncertainty, not a high-confidence AI accusation.
All six live labels were uncertain. The four assignment examples are short; the
longer synthetic template also elicited semantic uncertainty. No live likely-AI
or likely-human outcome is claimed. Controlled endpoint tests separately verify
all three exact label branches.

The ensemble formulas, thresholds, system prompt and sample texts were unchanged
for this run. No repeated selection of favorable responses or tuning to produce
a desired label was performed. These observations are not an empirical accuracy
or calibration study. UTC timestamps cross into October 21; the local project date
remains October 20 in America/New_York.
