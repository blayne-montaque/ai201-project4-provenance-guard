# Provenance Guard

**CodePath AI201 / CSCI 485 Project 4** · Repository name:
`ai201-project4-provenance-guard`

A local Flask backend that accepts creative work, combines three distinct
assessment signals, communicates uncertainty, and lets creators appeal. SQLite
preserves the original decisions and their history. The system supports a creator
verification credential, an analytics dashboard, and structured creative-work
metadata as a second input type.

**Writing style cannot prove authorship.** Scores are uncalibrated estimates, not
probabilities established against labeled reference data. No result is definitive.

## Project status

The seven required backend features and all four stretch implementations are
present. The planning document was committed before application code; every
stretch has its own earlier planning-only commit. See
[repository audit](artifacts/repository_audit.md) for rubric evidence and limitations.

The required Groq Scout model actually returned **HTTP 404 `model_not_found`**.
[Sanitized failure evidence](artifacts/groq_smoke_scout.json) is retained. On
October 20, 2026, the project owner explicitly authorized `openai/gpt-oss-20b`.
Its [independent live smoke test](artifacts/groq_smoke_authorized.json) succeeded,
followed by six real endpoint submissions with live Groq assessments. The existing
private `.env` now selects that authorized model; the Scout default and failure
evidence remain available for reproduction. No automatic fallback is implemented.

Observed decision confidence ranges from **0.088171 to 0.864150**. All six live
results were `uncertain`: the high-confidence case supports withholding attribution,
not a confident AI accusation. All three directional/uncertain label branches are
separately demonstrated with explicit controlled fixtures. See the evidence below
and [model substitution record](artifacts/model_substitution.md).

The GitHub repository has not been created or pushed. No deployment, course
submission or video recording has been performed. The separate detailed grading
page was not provided; the checklist covers the complete supplied
[assignment](artifacts/assignment_source.txt) without inventing point allocations.

## Architecture and request lifecycle

The complete diagram and design decisions are in [planning.md](planning.md#architecture).

```text
POST /submit -> body/schema validation + per-IP limiter
  -> text: Groq semantic + stylometry + repeated phrases
  -> weighted score + sufficiency + agreement -> exact transparency label
  -> atomic SQLite content + audit event -> 201 JSON

POST /submit (metadata) -> schema/timeline consistency -> uncertain label
  -> same SQLite, appeals, quota, credential and analytics

POST /appeal -> lookup + creator-ID match + duplicate check
  -> atomic appeal + under_review status + original decision snapshot -> 201 JSON

SQLite -> GET /log, /content/<id>, /analytics, /dashboard
Registered token + expiring challenge -> certificate -> displayed on content
```

Flask-Limiter checks the quota before entering the view, so malformed requests
also count and an exhausted quota takes precedence over schema errors. The
database stores a SHA-256 of normalized input, the assessment and history, not
full submissions. Metadata uses canonical JSON for its hash. Audit records include
UTC timestamps, UUIDs, individual scores, attribution, confidence, current status
and whether an appeal has been filed. Appeal reasoning is intentionally retained.

## Windows PowerShell setup

Verified locally on Windows, Python **3.10.0**. Python 3.10+ is required. Start in
this repository's root. Keep an existing `.env`; do not overwrite its credentials.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Edit `.env` locally to set `GROQ_API_KEY`. Never paste it into a terminal command,
screenshot, README or Git. Activation is optional because commands call the
virtual environment's interpreter directly.

Launch on localhost:

```powershell
.\.venv\Scripts\python.exe -m flask --app provenance_guard:create_app run --host 127.0.0.1 --port 5000
```

Visit [health](http://127.0.0.1:5000/health) and
[dashboard](http://127.0.0.1:5000/dashboard). The Flask development server is for
local demonstration. No debug mode or public network binding is enabled here.

| Variable | Default | Purpose |
|---|---|---|
| `GROQ_API_KEY` | empty | Private Groq credential; absent means degraded analysis |
| `GROQ_MODEL` | `meta-llama/llama-4-scout-17b-16e-instruct` | Assignment-prescribed model |
| `ALLOW_ALTERNATE_MODEL` | `false` | Explicit opt-in after project authorization; only `openai/gpt-oss-20b` is accepted |
| `GROQ_TIMEOUT_SECONDS` | `20` | Per-request timeout; SDK retries disabled |
| `DATABASE` | `instance/provenance_guard.sqlite3` | Durable local SQLite file |
| `SUBMISSION_LIMITS` | `10 per minute;100 per day` | Shared quota across both content types |
| `RATELIMIT_STORAGE_URI` | `memory://` | Explicit Flask-Limiter storage |

Environment variables override `.env`. Secrets, `.venv`, caches, all SQLite
databases and `instance/` are ignored. `requirements.txt` pins direct dependencies;
`requirements.lock` pins the full installed set. SQLite, hashing and verification
use the Python standard library. The Groq SDK version follows the assignment's
recommended `0.15.0`; structured output is still strictly validated locally.

The project owner's explicit approval is recorded in this repository. The existing
local `.env` has the following model settings; when reproducing in a fresh checkout,
set them in the same PowerShell session or in the private `.env`:

```powershell
$env:GROQ_MODEL = 'openai/gpt-oss-20b'
$env:ALLOW_ALTERNATE_MODEL = 'true'
```

This selects one model. It never retries a failed request against another model.

## API reference

Responses are JSON except `/dashboard`. Mutations require `Content-Type:
application/json`. Unknown fields, duplicate JSON keys, NaN, incorrect types and
invalid Unicode are rejected. Text is limited to 20,000 trimmed characters, creator
IDs to 80 safe identifier characters, reasoning to 2,000 characters, and request
bodies to 128 KiB. IDs are UUIDs generated by the server.

| Method/path | Input | Successful result |
|---|---|---|
| `GET /health` | none | 200 service identity and `status: ok` |
| `POST /submit` | `creator_id`, `text`, optional `content_type: text` | 201 content record, signals, scores, label and certificate |
| `POST /submit` | `creator_id`, `content_type: metadata`, `metadata` | 201 separate metadata assessment |
| `GET /content/<content_id>` | content ID | 200 original assessment, current status, current credential |
| `GET /log?limit=50` | optional integer 1–200 | 200 `entries`, newest first |
| `POST /appeal` | `content_id`, `creator_id`, `creator_reasoning` | 201 `under_review`, appeal ID and original assessment |
| `POST /creators/register` | `creator_id` | 201 one-time verification token |
| `POST /verification/challenge` | `creator_id` | 201 challenge ID, nonce and five-minute expiry |
| `POST /verification/verify` | `creator_id`, `challenge_id`, `nonce`, `verification_token` | 201 certificate after successful proof |
| `GET /certificates/<certificate_id>` | certificate ID | 200 certificate with `valid: true` |
| `GET /analytics` | none | 200 aggregate real-record metrics |
| `GET /dashboard` | none | 200 responsive HTML dashboard |

Expected errors use `{"error":{"code":"...","message":"..."}}`: 400 invalid
input; 403 creator mismatch or failed verification; 404 unknown content, creator,
challenge or certificate; 409 duplicate appeal/registration or consumed challenge;
410 expired challenge; 413 oversized request body; 429 quota or challenge attempt
limit; 503 unavailable SQLite. Unknown routes/methods also return JSON errors.
A model outage returns **201 with a persisted, degraded uncertain assessment**,
because the submission was accepted and the local signals ran.

Submit and appeal in a second PowerShell terminal:

```powershell
$body = @{
    creator_id = 'demo-writer'
    text = 'The sun dipped below the horizon. I sat on the porch, coffee in hand, watching the neighborhood slowly go quiet.'
} | ConvertTo-Json
$submission = Invoke-RestMethod http://127.0.0.1:5000/submit -Method Post -ContentType 'application/json' -Body $body
$submission | ConvertTo-Json -Depth 12

$appeal = @{
    content_id = $submission.content_id
    creator_id = 'demo-writer'
    creator_reasoning = 'Please review the context and my original draft.'
} | ConvertTo-Json
Invoke-RestMethod http://127.0.0.1:5000/appeal -Method Post -ContentType 'application/json' -Body $appeal
Invoke-RestMethod "http://127.0.0.1:5000/content/$($submission.content_id)"
Invoke-RestMethod http://127.0.0.1:5000/log | ConvertTo-Json -Depth 12
```

Response fields include `content_id`, `creator_id`, `timestamp`, `content_type`,
`content_hash`, `status`, `appeal_filed`, `ai_likelihood_score`, `confidence`,
`attribution`, `label`, `signals`, `analysis_status`, `uncertainty_reasons` and
`certificate`. Text responses additionally include weights, evidence sufficiency,
signal spread and agreement. Full real response examples are linked below; the
example request above is intentionally short and therefore insufficient for a
directional attribution even if Groq is available.

## Detection signals and confidence

Each text signal is a separate function with a bounded score and diagnostics:

| Signal | Weight | Measurement and reason for inclusion | Blind spots |
|---|---:|---|---|
| Groq semantic | 50% | Holistic observable coherence/transitions; captures context beyond counting words | Model bias, prompt injection, formal human writing, edited AI output |
| Stylometry | 30% | Sentence-length variation, vocabulary diversity and punctuation variety; deterministic structural evidence | Poems, formal/non-native writing, language/segmentation bias |
| Repetition/predictability | 20% | Repeated trigram concentration and repeated two-word sentence openings; phrase reuse beyond structural regularity | Refrains and intentional repetition; varied AI prose evades it |

The semantic prompt treats submissions as untrusted data. The required JSON has
exactly `ai_likelihood` (finite number 0..1), `explanation` (1..400 characters),
`insufficient_evidence` (boolean), and `uncertainty` (boolean). Local validation
rejects missing/extra fields, strings as scores, booleans as numbers, malformed
JSON and truncated completions. Public explanations summarize observable
characteristics; raw service errors and credentials are never returned.

For stylometry, let CV be sentence-length population standard deviation divided
by mean, TTR be unique words / all words, and P be distinct punctuation characters:

```text
Y = 0.5*(1-min(CV,1)) + 0.3*(1-TTR) + 0.2*(1-min(P/6,1))
R = 0.7*(1-unique_trigrams/all_trigrams)
  + 0.3*(1-unique_two_word_openings/all_sentence_openings)
S = 0.50*Groq + 0.30*Y + 0.20*R
```

An empty repetition denominator contributes zero and insufficient evidence.
Signals are distinct measurements, **not statistically independent**. Repeated
word use may influence both TTR and phrase reuse. Weights are design choices:
semantic context gets the largest contribution, structure less, repetition least
because creative repetition is common. No tuning was done to force sample labels.

`ai_likelihood_score = S` is an **uncalibrated AI-likelihood estimate**. If any
required signal is unavailable, S is `null`, confidence is 0, and the label is
uncertain. Available scores remain visible; missing Groq is never replaced by 0
or renormalized away.

For all available signals:

```text
E = min(1, word_count/80) * min(1, sentence_count/3)
D = maximum_signal - minimum_signal
A = 1-D
X = abs(2*S-1)
```

A directional decision requires at least 80 words and three sentences, at least
50% alphabetic characters among non-whitespace characters, no signal declaring
insufficient evidence, no Groq uncertainty flag, and D ≤ 0.50. With those checks:

- S ≥ 0.85: `likely_ai`.
- S ≤ 0.15: `likely_human`.
- Otherwise: `uncertain`.

Missing/weak/conflicting evidence always yields `uncertain` with reasons.
Boundaries are inclusive and evaluated before display rounding.

`confidence = E*A*X` for a directional decision;
`confidence = E*(1-A*X)` for an uncertain decision. Confidence measures heuristic
support for **the reported decision**, not AI probability. High confidence in
uncertainty is possible when adequate signals conflict or center on S=0.5. A
value of 0.6 does not mean 60% accuracy. Extreme-score category names also do not
guarantee that this separate confidence field is close to 1.

We validate arithmetic, exact boundaries, missing/short/conflicting evidence and
label reachability with deterministic tests. We measure sample variation but have
not calibrated accuracy, precision, recall or fairness against a labeled corpus.
Production work would require consented reference data, language/genre-specific
evaluation, false-positive analysis and empirical calibration.

## Exact transparency labels

**High-confidence AI** (`likely_ai`):

> AI-generated content suspected. Multiple automated signals suggest AI involvement, but this assessment is not proof of authorship. The creator may request a review.

**High-confidence human** (`likely_human`):

> Likely human-written. Automated signals are consistent with human authorship, but this assessment cannot verify who created the content.

**Uncertain** (`uncertain`):

> Authorship uncertain. The available signals do not support a reliable AI-versus-human assessment. No definitive attribution is made.

## Observed submissions and audit evidence

<!-- BEGIN GENERATED EVIDENCE -->
Live execution with `openai/gpt-oss-20b`, captured 2026-10-21T00:03:55.004523+00:00.
These are observed API responses, not injected signal values. Input authorship is described in the source file; samples are not an accuracy benchmark.
| Submission | Raw AI estimate | Decision confidence | Attribution |
|---|---:|---:|---|
| assignment_polished | 0.3435714891966276 | 0.449816 | uncertain |
| assignment_casual | 0.17477598374197306 | 0.389044 | uncertain |
| assignment_formal | 0.4241860465116279 | 0.335547 | uncertain |
| assignment_edited | 0.3119243675932641 | 0.377476 | uncertain |
| synthetic_template | 0.608906779661017 | 0.864150 | uncertain |
| synthetic_short_poem | 0.38946699141100893 | 0.088171 | uncertain |

Full texts, diagnostics and responses: [live observations](artifacts/demo_live/observations.json).

The observed high/lower pair is **synthetic_template (0.864150, uncertain)** and **synthetic_short_poem (0.088171, uncertain)**. Confidence supports the reported decision, not an authorship probability.
All live examples in this run remain uncertain. The high-confidence case is **confident uncertainty**, not a high-confidence AI/human verdict. No live directional classification is claimed, and no threshold was tuned to manufacture one. The longer sample has adequate length but the semantic signal remains uncertain; the short poem's limited evidence lowers confidence.

Actual offline submissions exercised the real local signals, routes, SQLite and appeals with the API key deliberately absent. All six returned a null combined estimate and confidence 0, as specified for degraded analysis. Their local measurements still vary:

| Submitted example | Stylometry | Repetition | Decision confidence |
|---|---:|---:|---:|
| assignment_polished | 0.478572 | 0.000000 | 0.000000 |
| assignment_casual | 0.332587 | 0.000000 | 0.000000 |
| assignment_formal | 0.580620 | 0.000000 | 0.000000 |
| assignment_edited | 0.373081 | 0.000000 | 0.000000 |
| synthetic_template | 0.818333 | 0.442034 | 0.000000 |
| synthetic_short_poem | 0.564890 | 0.100000 | 0.000000 |

Full public texts and actual response objects: [offline observations](artifacts/demo_offline/observations.json). The assignment's four examples are all shorter than the 80-word sufficiency threshold; that conservative decision is preserved, not tuned away for a demonstration.

Controlled endpoint executions use deliberately injected fixed scores to verify branch reachability. These are **test fixtures, not model results**:

| Controlled submission | Raw estimate | Decision confidence | Attribution |
|---|---:|---:|---|
| high_ai | 0.95 | 0.90 | likely_ai |
| lower_uncertain | 0.65 | 0.70 | uncertain |
| high_human | 0.05 | 0.90 | likely_human |

[Controlled response evidence](artifacts/demo_controlled/observations.json) includes its fixture provenance on every signal. It demonstrates high/lower decision support and all three exact labels, without claiming empirical detection quality.

Three **actual SQLite audit entries** from the `live` run follow (a field projection for readability). [Full entries with diagnostics](artifacts/audit_sample.json) and [complete run log](artifacts/demo_live/audit_log.json) are committed. The third event is the appeal on the first submission; the first event remains classified.

```json
[
  {
    "event_id": 1,
    "event_type": "submission",
    "timestamp": "2026-10-21T00:03:55.566893+00:00",
    "content_id": "fd35aa7e-d70c-4313-b666-3c64cd57e2c1",
    "attribution": "uncertain",
    "ai_likelihood_score": 0.3435714891966276,
    "confidence": 0.449816,
    "status": "classified",
    "appeal_filed": false,
    "signal_scores": {
      "groq": 0.4,
      "repetition": 0.0,
      "stylometry": 0.4785716306554253
    }
  },
  {
    "event_id": 2,
    "event_type": "submission",
    "timestamp": "2026-10-21T00:03:56.327972+00:00",
    "content_id": "d85b379f-d43a-46db-8616-660ce93d140d",
    "attribution": "uncertain",
    "ai_likelihood_score": 0.17477598374197306,
    "confidence": 0.389044,
    "status": "classified",
    "appeal_filed": false,
    "signal_scores": {
      "groq": 0.15,
      "repetition": 0.0,
      "stylometry": 0.3325866124732435
    }
  },
  {
    "event_id": 7,
    "event_type": "appeal",
    "timestamp": "2026-10-21T00:03:59.927623+00:00",
    "content_id": "fd35aa7e-d70c-4313-b666-3c64cd57e2c1",
    "attribution": "uncertain",
    "ai_likelihood_score": 0.3435714891966276,
    "confidence": 0.449816,
    "status": "under_review",
    "appeal_filed": true,
    "signal_scores": {
      "groq": 0.4,
      "repetition": 0.0,
      "stylometry": 0.4785716306554253
    },
    "appeal_reasoning": "Demonstration appeal: please review the original draft and its context."
  }
]
```

Observed appeal response: `201`. The content subsequently returned `status: under_review`; its original scores were retained. The same run also issued a real local verification credential and submitted metadata, then rendered a dashboard from those records. Verification tokens/nonces are excluded from the evidence exports.
<!-- END GENERATED EVIDENCE -->

## Appeals and rate limiting

An appeal must match an existing content ID and its stored creator ID. A write
transaction begins before lookup; one unique appeal record, the `under_review`
status and a new audit event commit together. Tests inject an audit failure to
verify rollback and race two appeals to verify exactly one succeeds. The original
attribution, score, confidence and label remain intact. There is no automatic
reclassification or resolution endpoint; review is manual.

**Matching creator IDs is not authentication.** Anyone knowing an ID can claim it
in this demonstration. A trusted identity provider and authorization are required
for submission ownership, appeals, credentials, content retrieval and audit access
in production. The current review interface is `/log`, which includes reasoning.

The centralized default is **10 submissions/minute and 100/day per source IP**,
shared across text and metadata. Ten/minute permits revision bursts; 100/day allows
individual creative use while bounding automated Groq demand. Invalid requests
count; quota-rejected requests never invoke a signal or create a decision record.
Appeals have 20/minute; registration/challenges 5/minute; verification 10/minute.

[Actual localhost HTTP evidence](artifacts/http_smoke.json) records:

```text
201 201 201 201 201 201 201 201 201 201 429 429
```

The observed `429` body was
`{"error":{"code":"rate_limit_exceeded","message":"Too Many Requests"}}`,
with `Retry-After: 60`; exactly ten submission events persisted. These were actual
requests over localhost to a running server with Groq intentionally unavailable,
not synthetic status values. Creation uses 201 instead of the assignment's sample
200; both are successful HTTP responses.

Explicit `memory://` limiter storage is appropriate for one development process.
Counters reset on restart and do not coordinate multiple workers. Production needs
a shared backend such as Redis, authenticated creator quotas, spending controls
and a correctly configured trusted proxy. Forwarded IP headers are not trusted by
default; shared NAT addresses can share a quota.

## Stretch features

**Three-signal ensemble:** 50/30/20 weighting, documented distinct properties,
diagnostics, disagreement handling and no fabricated fallback. Tests cover all
labels with controlled signals. See [ensemble.py](provenance_guard/ensemble.py).

**Provenance certificate:** registration generates a 256-bit secret token, returned
once. The database holds a salted PBKDF2-HMAC-SHA256 verifier with 200,000 iterations.
A random challenge nonce expires in five minutes, is stored only as a hash, is
bound to its creator and becomes unusable after success or replacement. Five
failed attempts lock a challenge; constant-time comparisons verify token and
nonce. Successful proof issues a persistent certificate containing certificate
ID, creator ID, method, UTC issue time and verification status. Content shows the
current credential even if submitted before verification.

The display says **Verified secret control (demo)**. Public self-registration does
not establish that a creator is human, owns a real-world identity, or wrote the
associated text. This deliberately limited implementation of the assignment's
"verified human" credential concept follows the implementation brief's prohibition
on inventing identity verification. IDs are first-come; token recovery, revocation
and real identity enrollment are not implemented. Outside localhost use HTTPS
because verification transmits the original token. Never publish token/nonce values.

```powershell
$identity = @{ creator_id = 'certificate-demo' } | ConvertTo-Json
$registration = Invoke-RestMethod http://127.0.0.1:5000/creators/register -Method Post -ContentType 'application/json' -Body $identity
$challenge = Invoke-RestMethod http://127.0.0.1:5000/verification/challenge -Method Post -ContentType 'application/json' -Body $identity
$proof = @{
    creator_id = 'certificate-demo'
    challenge_id = $challenge.challenge_id
    nonce = $challenge.nonce
    verification_token = $registration.verification_token
} | ConvertTo-Json
$certificate = Invoke-RestMethod http://127.0.0.1:5000/verification/verify -Method Post -ContentType 'application/json' -Body $proof
Invoke-RestMethod "http://127.0.0.1:5000/certificates/$($certificate.certificate_id)"
```

**Analytics dashboard:** `/dashboard` and `/analytics` derive attribution counts,
appeals count/rate, mean confidence, uncertainty rate, disagreement rate and
content-type counts from actual SQLite records. The denominator is unique
submissions, not audit events. Empty databases render zero values. No external
chart scripts or fabricated data are used. Confidence averages mix reported
decisions and metadata's zero confidence and therefore are not accuracy metrics.

**Second modality:** the assignment explicitly accepts structured metadata.
Submit [examples/metadata.json](examples/metadata.json) with `content_type:
metadata`. Required metadata fields are title (1..200), medium (`image`, `audio`,
`video`, `mixed_media`), tools (0..20 names, each ≤80), creation_steps (1..20 objects
with description ≤500 and timezone-aware ISO timestamp), and ai_disclosure
(`none`, `assisted`, `generated`, `undisclosed`). This separate local path reports
duplicate descriptions, out-of-order steps and future timestamps. It does not
call Groq, examine media or infer authorship from unverified declarations. It
returns null AI score, confidence 0, `metadata_only` and the exact uncertain label.
Persistence, appeals, limits, credentials and analytics work for this modality too.

```powershell
$metadata = Get-Content -Raw -Encoding UTF8 examples/metadata.json
Invoke-RestMethod http://127.0.0.1:5000/submit -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($metadata))
```

## Reproducing tests and evidence

Latest observed local run: **131 passed, 0 failed, 0 skipped** (October 20, 2026).
[Machine-readable pytest result](artifacts/pytest-results.xml) is committed.
`pip check` reported no broken requirements. Real localhost HTTP startup and
dashboard requests both returned 200; submission quota results are recorded above.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m scripts.demo --mode offline
.\.venv\Scripts\python.exe -m scripts.demo --mode controlled
.\.venv\Scripts\python.exe -m scripts.http_smoke
# Live, using the prescribed model (records actual sanitized failures too):
.\.venv\Scripts\python.exe -m scripts.smoke_groq
# Authorized alternate-model smoke check:
.\.venv\Scripts\python.exe -m scripts.smoke_groq --model openai/gpt-oss-20b --output artifacts/groq_smoke_authorized.json
# Live endpoint evidence with the authorized model configuration:
.\.venv\Scripts\python.exe -m scripts.demo --mode live
```

Each demo creates a new ignored database under `instance/`; existing application
records are not overwritten. Default evidence output paths are replaced on rerun;
use `--output artifacts/my-run` to preserve another run. Offline mode removes the
key from that app's configuration only. Controlled mode injects documented fixed
signal scores and never pretends to run Groq. Live mode uses the configured API
without fake scores. Public bundled examples include assignment examples and
explicitly Codex-generated samples; none is an independently verified human corpus.

The pytest suite uses temporary databases and injected clients, never live calls
or paid API access. It covers signal output validation, exact score boundaries,
four assignment samples plus poems, conflicting/insufficient evidence, endpoint
contracts, Unicode/body limits, persistence, atomic rollback, concurrent appeals,
quota headers/429, challenge replay/expiry/lockout, analytics and metadata. A
GitHub Actions workflow is supplied for offline tests; it has **not been run on
GitHub** because this repository has not been published.

## Known limitations and likely mistakes

- A human-written repetitive litany could score high on uniform sentence lengths,
  low vocabulary diversity, repeated trigrams and repeated openings. If Groq also
  interprets that style as machine-like, even the ensemble can falsely suspect AI.
  Short-poem safeguards help, but a long refrain can pass the length threshold.
- Formal non-native or academic writing can trigger structural/semantic suspicion.
  A casually edited AI text may evade these signals entirely. The casual sample's
  source label is supplied by the assignment, not independently verified here.
- Word/sentence heuristics favor alphabetic text with familiar punctuation; many
  languages and unconventional poetry are poorly represented. A word-count cutoff
  is a conservative design choice, not a validated threshold for reliable detection.
- Prompt separation and strict schemas reduce malformed outputs but cannot prevent
  every prompt-injection attempt or biased semantic judgment. No empirical
  calibration, adversarial robustness or fairness study has been performed.
- SQLite audit events are append-only through the application, not cryptographically
  tamper-proof against a database administrator. Runtime data is sensitive and not
  automatically expired. There is no production authentication or moderation queue.
- Metadata can be fabricated and credential registration can be impersonated.
  Neither feature proves humanity or authorship. The dashboard reports decisions,
  not ground truth. No image/audio analysis is claimed.

## Spec reflection and AI usage

**How planning helped:** the spec separated raw AI-likelihood from decision
confidence and required a degraded result when Groq was missing. The actual Scout
404 therefore had a defined outcome before it happened; the implementation did
not turn an API failure into a human verdict. Planning also made original-score
preservation an atomic requirement for appeals.

**Actual deviations:** the conceptual submission diagram puts validation before
the limiter, while Flask-Limiter rejects exhausted quotas before view validation;
this counts malformed traffic and protects request-processing capacity. Record
creation returns 201 instead of the assignment's illustrative 200. The credential
is explicitly secret-control verification rather than an unsupported claim that
registration proves humanity. None of these changes is hidden.

The actual Scout 404 also required the model substitution anticipated by the plan.
After explicit owner approval, the project selected `openai/gpt-oss-20b` and captured
its real outputs. The scoring functions, thresholds and prompts were not altered
to force a live directional label. The longer synthetic template produced high
support for uncertainty, while the short poem produced low support; both preserve
the limitations stated in the original confidence definition.

Codex assisted with the following work; this disclosure does not claim human
review or approval of generated code:

1. Using the signal contracts and architecture, Codex generated the Groq wrapper,
   factory, validators and persistence layer. It checked these with independent
   signal tests before endpoint integration. The output validator was made strict
   about finite numeric scores, duplicate JSON keys, truncated responses and
   exception redaction instead of trusting the service's JSON mode.
2. Using the scoring and uncertainty sections, Codex generated deterministic
   stylometry/repetition functions and the ensemble. It verified four contrasting
   assignment inputs, exact inclusive thresholds and all label branches. Decimal
   weighting avoids floating-point addition changing a boundary decision. The
   formulas were retained despite examples shorter than the sufficiency cutoff.
3. Using the appeals and rate-limit sections, Codex generated transactions and
   Flask-Limiter integration. Initial testing found a real `ReferenceError` when
   disabled limiter wrappers outlived their object. Codex revised the factory to
   retain a strong reference in `app.extensions`, then reran the failing workflow
   suite successfully. Concurrency and rollback checks verify more than happy paths.

Commits use the explicit automated author `Codex <codex@local.invalid>` rather than
inventing a human review/commit history. Git was initialized locally after
inspection. Planning chronology is documented in the repository audit.

## Portfolio walkthrough

**Video: not yet recorded.** The project owner will record and link it manually.
Suggested two-minute route: show planning/history, submit a work, explain score
and uncertainty, file an appeal and inspect the retained decision, show a `429`,
then briefly show the dashboard, metadata and credential limitations. Explain that
the real examples show high versus low support for an uncertain decision, while
controlled fixtures exercise the other two labels. Publish the GitHub repository
and submit the repository/video links through the Course Portal after review.

## Reference documentation

Implementation references: [Groq Scout model documentation](https://console.groq.com/docs/model/meta-llama/llama-4-scout-17b-16e-instruct/)
for the prescribed model interface; [Groq structured outputs](https://console.groq.com/docs/structured-outputs)
for JSON output behavior; [Flask-Limiter configuration](https://flask-limiter.readthedocs.io/en/stable/configuration.html)
for explicit storage and headers; [Flask-Limiter recipes](https://flask-limiter.readthedocs.io/en/stable/recipes.html)
for JSON `429` handling. Actual model availability is documented from this account's
API responses, not inferred from a documentation listing.
