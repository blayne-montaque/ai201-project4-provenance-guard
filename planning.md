# Provenance Guard — implementation plan

Project/repository name: `ai201-project4-provenance-guard`.
Written October 20, 2026, before application code. Source of requirements: the
complete CodePath AI201 Project 4 assignment supplied as a text attachment,
plus the user's implementation brief. The separately linked grading page was
not supplied; this plan covers every requirement visible in the assignment
without inventing a point allocation. The portfolio video, GitHub publication,
and course submission remain manual tasks.

## Scope and principles

Build a local Flask backend for creative text, a conservative multi-signal
assessment, three reader-facing labels, transactional appeals, a durable SQLite
audit history, and Flask-Limiter abuse controls. Style cannot prove authorship.
All estimates are uncalibrated; no test demonstrates population-level detection
accuracy. Distinct signals can still be correlated. False positives harm creators,
so extreme scores alone are insufficient: adequate text and signal agreement
are required before either directional label is returned.

The existing workspace contains only a private `.env`. Preserve it; never display
its values or commit it. Windows and Python 3.10.0 are installed. Create a local
virtual environment. Use Flask, Flask-Limiter, Groq, python-dotenv, pytest and
built-in SQLite/statistics/cryptography primitives where appropriate. Pin the
resolved dependency set for reproduction. No remote creation, push or deployment.

## Architecture

```text
POST /submit {creator_id, text}
  | body/schema validation (bounded JSON, nonempty strings)
  v
shared per-IP rate limiter (10/minute;100/day)
  | validated text
  +--> Groq semantic assessment ------> score or unavailable + reason
  +--> stylometry --------------------> score + numeric diagnostics
  +--> lexical patterns (stretch 1) ---> score + numeric diagnostics
  | three Signal records
  v
weighted ensemble + sufficiency + disagreement
  | raw estimate, decision confidence, attribution, uncertainty reasons
  v
exact transparency-label mapping
  | unique ID + original assessment + label + content hash
  v
SQLite transaction: content record + submission audit event
  | committed public assessment (no full submitted text)
  v
JSON response --> creator/reader

POST /appeal {content_id, creator_id, creator_reasoning}
  | validated fields
  v
SQLite transaction: lookup content --> verify stored creator matches
  | existing original assessment; reject unknown/mismatched/active duplicate
  v
status = under_review + persistent appeal + audit snapshot
  | original scores/label retained, reasoning and appeal ID added
  v
JSON confirmation; GET /log exposes structured chronological evidence
```

A submission passes validated text to independent signal functions; the ensemble
communicates score, agreement and evidence limitations before persisting a label
and its complete decision history. An appeal looks up that original record,
checks the demonstration's creator ID, and atomically saves the reasoning, status
change and audit event. Readers and reviewers can inspect the original assessment
through the content and log endpoints without rerunning the model.

## Detection signals

All signals return `{name, score, available, insufficient_evidence, diagnostics}`.
Available scores are finite numbers in [0,1]; unavailable scores are `null`.
Diagnostic values are bounded public metrics or sanitized service error codes.

1. **Groq semantic assessment (50%)**: holistic coherence, transitions and textual
   characteristics. First attempt `meta-llama/llama-4-scout-17b-16e-instruct`.
   Request JSON with exactly `ai_likelihood`, `explanation`,
   `insufficient_evidence`, `uncertainty`. Validate types, bounds, finite numbers,
   unknown fields and explanation length locally; do not trust JSON mode alone.
   Explanation is brief observable evidence, not hidden reasoning or proof.
   Treat submitted text as untrusted data, never instructions. Temperature zero,
   bounded output, explicit timeout, no SDK retries to multiply traffic.
   No automatic model fallback. If the required model returns an error, retain
   sanitized status/code/model evidence. `openai/gpt-oss-20b` requires explicit
   user authorization and an availability check before use.
   Blind spots: prompt injection, language bias, polished human writing, edited
   AI writing and unreliable judgments about authorship.
2. **Stylometry (30%)**: sentence-length coefficient of variation, type-token
   ratio and punctuation variety. Candidate formula, fixed before sample testing:
   `0.5*(1-min(CV,1)) + 0.3*(1-TTR) + 0.2*(1-min(punctuation_kinds/6,1))`.
   Unicode word tokenization and sentence splitting are deterministic heuristics.
   No repeated n-grams or sentence openings in this signal. Formal prose and
   non-native writing may look uniform; poems, short text and other languages
   violate the assumptions. Low vocabulary diversity is not proof of AI use.
3. **Repetition/predictability (20%, stretch 1)**: repeated trigram concentration
   and repeated first-two-word sentence openings. Formula:
   `0.7*(1-unique_trigrams/total_trigrams) + 0.3*(1-unique_openings/total_openings)`.
   Empty denominators produce zero with insufficient evidence. This measures
   phrase reuse, not sentence lengths, vocabulary diversity or punctuation.
   Refrains and intentional literary repetition may score highly; varied AI
   output may score near zero. No claim of statistical independence.

Implement/test Groq alone in checkpoint A. Test stylometry independently with
formal, casual, short-poem and borderline inputs before integrating checkpoint B.
Stretch 1 requires its own dated planning-only commit before implementation in B.

## Uncertainty representation and exact mathematics

With all signals available, `S = 0.50*G + 0.30*Y + 0.20*R` is
`ai_likelihood_score`, an **uncalibrated AI-likelihood estimate**. Use full
precision for decisions; round public diagnostics to six decimals only afterward.
If any required signal is unavailable, `S = null`, retain the available individual
scores, return `uncertain` with confidence zero and a degraded-analysis reason;
do not renormalize away the missing semantic evidence.

Let `N` be word count and `K` sentence count. Evidence sufficiency
`E = min(1,N/80) * min(1,K/3)`; adequate text requires N >= 80 and K >= 3.
Let `D = max(G,Y,R)-min(G,Y,R)` and agreement `A = 1-D`.
Disagreement is significant when D > 0.50. All signal insufficient-evidence flags
and Groq's uncertainty flag block directional labels. Less than 50% alphabetic
characters among non-whitespace characters also blocks a directional decision.

With adequate evidence, no signal flags and D <= 0.50:
- S >= 0.85 => `likely_ai` (inclusive).
- S <= 0.15 => `likely_human` (inclusive).
- Otherwise => `uncertain`.
All failed adequacy/agreement checks => `uncertain`, with explicit reasons.

Let extremity `X=abs(2*S-1)`. `confidence` measures support for the *reported
decision*, not probability of AI authorship. For a directional decision,
`confidence = E*A*X`; for `uncertain`, `confidence = E*(1-A*X)`.
Thus confident uncertainty is possible when sufficient but conflicting or central
evidence prevents attribution. Short text reduces both kinds of confidence.
No score is calibrated to empirical correctness. A confidence of 0.6 is a
heuristic support value in this formula, not a 60% chance of true authorship.
The `attribution`, raw score and reasons must always accompany confidence.

## Transparency labels

**High-confidence AI**

"AI-generated content suspected. Multiple automated signals suggest AI involvement, but this assessment is not proof of authorship. The creator may request a review."

**High-confidence human**

"Likely human-written. Automated signals are consistent with human authorship, but this assessment cannot verify who created the content."

**Uncertain**

"Authorship uncertain. The available signals do not support a reliable AI-versus-human assessment. No definitive attribution is made."

Map these exact strings by attribution. Test all three using controlled signal
outputs without presenting fixtures as live model success.

## API and storage contracts

- `GET /health`: startup and service identity (no secrets).
- `POST /submit`: JSON `{text, creator_id}`, optional `content_type: "text"`.
  Text 1..20,000 characters after trimming; creator ID 1..80 safe identifier
  characters. Return 201 with UUID, timestamps, modality, original assessment,
  exact label, `status: classified`, signal diagnostics and uncertainty reasons.
- `GET /content/<content_id>`: stored assessment and current status; 404 unknown.
- `GET /log?limit=50`: recent structured events, bounded limit 1..200.
- `POST /appeal`: `{content_id, creator_id, creator_reasoning}`; reasoning 1..2000
  characters. 201 accepted, 404 unknown, 403 mismatched creator, 409 active duplicate.
  Use the assignment's `creator_reasoning` field and `appeal_reasoning` in events.
- Malformed JSON/schema/missing/empty/oversized field => 400. Request body over
  128 KiB => 413. Rate violation => 429 plus rate headers. Predictable
  `{error: {code, message}}` for all expected API errors; no exception reprs.

SQLite tables: contents (ID, creator, timestamp, type, SHA-256, original assessment
JSON, status); appeals (ID, content foreign key, creator, reason, timestamp,
status); audit_events (sequence, type, content reference, timestamp, JSON snapshot).
Use parameterized SQL, foreign keys, bounded connection timeout and transactions.
Audit events include individual scores, combined score, confidence, attribution,
status and appeal flag; never full submission text, API keys or verification
secrets. Appeal reasoning is deliberately stored for reviewers. Creator IDs,
reasoning and public explanations are private runtime data: database is ignored.

## Appeals workflow and edge cases

Begin a SQLite write transaction before content lookup. Verify content and creator,
prevent duplicates with a database uniqueness constraint, insert the appeal,
update status and append an immutable snapshot including the original decision.
Rollback the entire transaction if any write fails. A reviewer sees creator
reasoning, original signals, confidence, uncertainty reasons and time history.
No automated reclassification or review-resolution endpoint is required.

Creator ID matching is **not authentication**. An attacker who knows an ID can
impersonate it. Use a trusted identity provider and authorization in production;
protect `/log`, content retrieval, verification and analytics before deployment.

Anticipated cases and responses:
- Short poems/refrains: insufficient-evidence flag or disagreement => uncertain.
- Formal human prose: potential false positive; extreme threshold and appeals.
- Lightly edited AI prose: possible false negative; no proof-of-human claims.
- Unknown appeal content: 404, no partial record.
- Duplicate/racing appeals: one active appeal; others 409.
- Groq outage, missing credentials, malformed response: null combined score,
  uncertain, sanitized explanation, persist actual local measurements.
- Prompt injection: system/data separation and strict schema; still a limitation.

## Rate limits and operational safeguards

Use explicit Flask-Limiter `storage_uri="memory://"` by default and central
configuration for 10 submissions/minute and 100/day, shared across submission
modalities per source IP. Ten/minute accommodates revising a piece; 100/day limits
automated API spending beyond typical individual use. Malformed requests count,
so the framework limiter may reject before validation: this operational ordering
protects parsing/model capacity. Do not trust forwarded IP headers by default.
Memory counters reset on restart and are per process; production needs shared
Redis, trusted proxy configuration, authenticated quotas and monitoring.

## AI Tool Plan

| Milestone | Spec supplied to Codex | Generated work | Verification / anticipated revision |
|---|---|---|---|
| M3 | Detection signal 1, Architecture, API/storage contracts | Flask factory/config, validated Groq function, submission route, SQLite/log | Test signal directly with valid, malformed and unavailable responses before wiring it; check UUIDs, persistence, response schema, timeout and secret redaction. Model access may require explicit authorized substitution. |
| M4 | Detection signals, Uncertainty representation, Architecture | Standalone stylometry, stretch lexical signal, weighted ensemble | Four assignment-style samples plus poem; verify formula by hand, exact thresholds and contradictory outputs; reject intuition-based tuning or fabricated labels. |
| M5 | Transparency labels, Appeals workflow, Architecture, Rate limits | Exact label mapping, transactional appeal endpoint, limiter and audit | All labels reachable via injected signals, immutable original verdict, concurrent/duplicate appeal checks, real 429 and restart durability. Revise transaction/validation defects found by tests. |

This is a forward-looking tool plan. Codex generates and checks implementation;
no human review, approvals, or external label feedback are claimed unless actually
provided. Document concrete generated work and actual revisions in README.

## Verification and delivery sequence

1. Commit this file alone, before application files.
2. A: app skeleton, independently tested Groq signal, storage/log; test and commit.
3. Before B: dated stretch-1 planning addition and separate commit. B: standalone
   stylometry, lexical signal and ensemble; test and commit.
4. C: labels, appeals, limiter; workflow tests and commit.
5. Each remaining stretch gets a dated design/acceptance addition and planning-only
   commit before its implementation, then tests and an implementation commit.
6. Produce real runtime evidence with explicit live/degraded/fixture provenance;
   never confuse controlled test outputs with live classifications. Save at least
   two submissions, three audit events including an appeal, and 429 statuses.
7. Re-read assignment, run full pytest, check tracked secrets/ignored `.env`, audit
   Git ordering, document all missing evidence and manual deliverables.

Tests cover input bounds/types; signal schema and outages; four varied texts;
formula and exact thresholds; disagreement/short text; all labels; restart
persistence; transaction rollback and appeals; 429; certificate challenges;
analytics and a second content type; application startup. Use Flask test client
and injected clients, no paid API required. Live Groq smoke is separate.

## Stretch roadmap (implementation not yet authorized by a planning checkpoint)

1. Three-signal ensemble as designed above.
2. Challenge-response certificate demonstrating control of a registered secret.
   Display as a creator verification credential; never claim proof of humanity,
   identity or text authorship. Public self-registration alone cannot verify a
   human; explicitly disclose that gap in the assignment's "verified human" idea.
3. Local HTML analytics dashboard backed by real SQLite aggregations.
4. Structured creative-work metadata, explicitly accepted by the assignment as a
   second content type; validate metadata and perform consistency checks in a
   separate path. Never describe metadata validation as image/audio inspection.

Each concrete stretch design and acceptance criteria will follow in a dated
subsection before its code exists.

## Stretch 1 — ensemble detection — October 20, 2026

Design checkpoint, after A and before B: implement the three distinct signals and
50/30/20 weights already specified above. Lexical phrase repetition has its own
function and diagnostics; it must not reuse stylometric CV/TTR/punctuation as its
score. Missing semantic evidence yields a null combined score and an uncertain
label; disagreement greater than 0.50 prevents directional attribution.

Acceptance: independently test stylometry on formal/casual/poem/borderline samples
before integration; verify weighted math and inclusive 0.15/0.85 boundaries;
exercise all three exact labels with controlled signal outputs, plus disagreement,
model uncertainty, insufficient text, missing Groq and nonalphabetic input.
Run four assignment examples without claiming their claimed authorship is ground
truth. Preserve fixed formulas even when a sample challenges intuition.
