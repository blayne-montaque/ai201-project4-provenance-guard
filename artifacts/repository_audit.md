# Repository audit

Generated 2026-10-20T21:01:13.681345+00:00. Snapshot HEAD: `9d80fbe`.
This file is generated before its own final audit commit; that commit cannot contain its own hash.

## Assignment review

Re-read the supplied complete assignment and mapped every visible feature/deliverable below. The separate course grading page/link was not supplied, so no exact earned-point claim is made. The stated target is 25 required + 4 stretch points; grading remains the instructor's decision.

| Requirement | Evidence / status |
|---|---|
| Planning (separately graded, 4 points in supplied assignment) | planning.md: signals, exact math, labels, appeals/edge cases, Architecture and AI Tool Plan; chronology verified below |
| Submission endpoint | provenance_guard/app.py; tests/test_api.py; saved response artifacts |
| At least two distinct signals | Groq semantic, stylometry and lexical repetition modules; independent signal tests |
| Confidence and uncertainty | ensemble.py and test_ensemble.py; inclusive thresholds, low evidence and disagreement tests; uncalibrated status explicit |
| Three transparency labels | Exact strings present in planning.md, README and labels.py; three endpoint fixture branches exercised |
| Appeals | Transactional store.appeal; creator match, unknown/duplicate, race and rollback tests; real appeal audit record |
| Rate limiting | Explicit memory storage; 10/minute and 100/day; real localhost HTTP 201×10 then 429×2 |
| Structured audit log | artifacts/audit_sample.json: at least three real events including appeal, original scores retained |
| Two observed submissions with high/lower confidence | PENDING: successful live examples with high/lower confidence; controlled examples are separately labeled and do not substitute for live evidence |
| README | Architecture, setup, APIs, signals/math, exact labels, actual evidence, limitations, reflection, AI usage, manual video placeholder |
| Stretch 1: ensemble | Three signals with 50/30/20 weights and independent diagnostics |
| Stretch 2: provenance certificate | Expiring one-use challenge + registered token, persistent certificate and content display; verifies secret control ONLY, not humanity/authorship |
| Stretch 3: dashboard | Real SQLite attribution/appeal/confidence/uncertainty metrics; tests/test_analytics.py |
| Stretch 4: second modality | Structured metadata explicitly accepted by assignment; separate validation/consistency path, tests/test_metadata.py |
| GitHub repository link | MANUAL: local Git repository only; no remote creation or push authorized |
| Portfolio video | MANUAL: not recorded, as instructed by project owner |
| Course submission | MANUAL: not performed |

## Automated repository checks

| Check | Result |
|---|---|
| First commit contains planning.md only | PASS |
| All three exact labels appear in README and planning | PASS |
| Stretch 1 planning-only commit predates implementation | PASS |
| Stretch 2 planning-only commit predates implementation | PASS |
| Stretch 3 planning-only commit predates implementation | PASS |
| Stretch 4 planning-only commit predates implementation | PASS |
| Private .env ignored and untracked | PASS |
| No runtime databases, venv or caches tracked | PASS |
| Tracked content does not contain private Groq key or key-shaped literals | PASS |
| No Git remote configured | PASS |
| At least three real structured audit entries, including appeal | PASS |
| Audit entries retain scores, attribution and timestamps | PASS |
| Real HTTP default quota observed 10 successes then 2 rejections | PASS |
| Saved full pytest run has zero failures/errors/skips | PASS |
| All label variants reachable in explicitly controlled endpoint tests | PASS |

Saved test result: **131 tests, 0 failures/errors, 0 skipped**. See pytest-results.xml. All tests are offline; no live success is inferred from mocks.

## Planning chronology

Initial planning-only commit: `50afee8`.

| Stretch | Planning commit | First implementation | Ordering |
|---|---|---|---|
| 1 | `494a884` | `83e8fd1` | Pass |
| 2 | `67a1a28` | `f3d08c1` | Pass |
| 3 | `604f297` | `f2f3f04` | Pass |
| 4 | `3fac695` | `13c9038` | Pass |

## Commit history at snapshot

```text
50afee8 docs: record architecture and implementation plan before code
50edc5b feat: checkpoint A validated Groq signal and persistent submission API
494a884 docs: plan stretch 1 ensemble before implementation
83e8fd1 feat: checkpoint B three-signal ensemble with explicit uncertainty
f39c451 feat: checkpoint C transactional appeals audit trail and rate limits
67a1a28 docs: plan stretch 2 secret-control credential before implementation
f3d08c1 feat: verify token control with expiring one-use provenance challenges
604f297 docs: plan stretch 3 SQLite analytics dashboard before implementation
f2f3f04 feat: render real SQLite detection and appeal analytics
3fac695 docs: plan stretch 4 structured metadata before implementation
13c9038 feat: analyze structured creative-work metadata as a second modality
9d80fbe test: capture reproducible API evidence and document honest limitations
```

## Verification limitations and remaining tasks

- Scout live attempt returned HTTP 404 model_not_found; sanitized evidence is committed. Alternate model availability is distinct from permission to use it.
- PENDING: successful live examples with high/lower confidence.
- Local token control is not a verified-human credential; the scope is disclosed, not fabricated.
- No empirical accuracy/calibration claims, verified human corpus, public deployment or human code-review claims.
- GitHub Actions is supplied but not claimed to have run remotely.
- Owner must review, record video, create/push GitHub repository when authorized and submit course links.

## Working tree inspection

Tracked/staged changes immediately before this report was written:
```text
M README.md
?? artifacts/repository_audit.md
```

Final delivery checks run after committing this report verify a clean working tree. Private ignored files remain outside Git by design.
