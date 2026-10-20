"""Check local repository chronology, evidence and secret exclusion; emit report."""
import json
import re
import subprocess
import xml.etree.ElementTree as ET

from dotenv import dotenv_values

from provenance_guard.config import ROOT
from provenance_guard.labels import LABELS
from provenance_guard.storage import utcnow


def git(*args):
    return subprocess.check_output(["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
                                   cwd=ROOT, text=True, encoding="utf-8").strip()


def main():
    tracked = git("ls-files").splitlines()
    commits = git("rev-list", "--reverse", "HEAD").splitlines()
    subjects = {commit: git("show", "-s", "--format=%s", commit) for commit in commits}
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    plan = (ROOT / "planning.md").read_text(encoding="utf-8")
    checks = []

    def check(label, condition):
        checks.append((label, bool(condition)))

    first_files = git("diff-tree", "--root", "--no-commit-id", "--name-only", "-r", commits[0]).splitlines()
    check("First commit contains planning.md only", first_files == ["planning.md"])
    check("All three exact labels appear in README and planning", all(label in readme and label in plan for label in LABELS.values()))
    stretch_files = {1: "provenance_guard/repetition.py", 2: "provenance_guard/verification.py",
                     3: "provenance_guard/templates/dashboard.html", 4: "provenance_guard/metadata.py"}
    chronology = []
    for number, file in stretch_files.items():
        planned = next(commit for commit in commits if subjects[commit].startswith(f"docs: plan stretch {number} "))
        implemented = git("log", "--diff-filter=A", "--format=%H", "--", file).splitlines()[-1]
        files = git("diff-tree", "--no-commit-id", "--name-only", "-r", planned).splitlines()
        good = commits.index(planned) < commits.index(implemented) and files == ["planning.md"]
        check(f"Stretch {number} planning-only commit predates implementation", good)
        chronology.append(f"| {number} | `{planned[:7]}` | `{implemented[:7]}` | {'Pass' if good else 'FAIL'} |")
    check("Private .env ignored and untracked", ".env" not in tracked and git("check-ignore", ".env") == ".env")
    private_tracked = [name for name in tracked if name.startswith((".venv/", "instance/", ".pytest_cache/"))
                       or re.search(r"\.(sqlite3?|db)(-|$)", name)]
    check("No runtime databases, venv or caches tracked", not private_tracked)
    # Compare without emitting the key or matching source text, even on failure.
    key = dotenv_values(ROOT / ".env").get("GROQ_API_KEY", "")
    secret_hits = []
    for name in tracked:
        path = ROOT / name
        if path.is_file():
            data = path.read_bytes()
            if key and len(key) > 8 and key.encode() in data:
                secret_hits.append(name)
            if re.search(rb"gsk_[A-Za-z0-9]{20,}", data):
                secret_hits.append(name)
    check("Tracked content does not contain private Groq key or key-shaped literals", not secret_hits)
    check("No Git remote configured", git("remote") == "")
    events = json.loads((ROOT / "artifacts" / "audit_sample.json").read_text())["entries"]
    check("At least three real structured audit entries, including appeal", len(events) >= 3
          and any(event["event_type"] == "appeal" for event in events))
    check("Audit entries retain scores, attribution and timestamps", all(
        {"timestamp", "content_id", "attribution", "confidence", "signals"} <= event.keys() for event in events))
    http = json.loads((ROOT / "artifacts" / "http_smoke.json").read_text())
    check("Real HTTP default quota observed 10 successes then 2 rejections", http["statuses"] == [201] * 10 + [429] * 2)
    xml = ET.parse(ROOT / "artifacts" / "pytest-results.xml").getroot()
    suites = list(xml.iter("testsuite"))
    total = sum(int(suite.get("tests", 0)) for suite in suites)
    failures = sum(int(suite.get("failures", 0)) + int(suite.get("errors", 0)) for suite in suites)
    skipped = sum(int(suite.get("skipped", 0)) for suite in suites)
    check("Saved full pytest run has zero failures/errors/skips", total > 0 and failures == skipped == 0)
    controlled = json.loads((ROOT / "artifacts" / "demo_controlled" / "observations.json").read_text())
    check("All label variants reachable in explicitly controlled endpoint tests",
          {item["response"]["attribution"] for item in controlled["submissions"]} == set(LABELS))
    live_path = ROOT / "artifacts" / "demo_live" / "observations.json"
    live = json.loads(live_path.read_text()) if live_path.exists() else None
    live_records = [item["response"] for item in live["submissions"]] if live else []
    successful = [record for record in live_records if record.get("analysis_status") == "complete"]
    varied = len(successful) >= 2 and max(r["confidence"] for r in successful) - min(r["confidence"] for r in successful) >= .2
    live_status = "Observed live examples with confidence variation" if varied else "PENDING: successful live examples with high/lower confidence"
    head = git("rev-parse", "--short", "HEAD")
    lines = ["# Repository audit", "", f"Generated {utcnow()}. Snapshot HEAD: `{head}`.",
             "This file is generated before its own final audit commit; that commit cannot contain its own hash.",
             "", "## Assignment review", "",
             "Re-read the supplied complete assignment and mapped every visible feature/deliverable below. "
             "The separate course grading page/link was not supplied, so no exact earned-point claim is made. "
             "The stated target is 25 required + 4 stretch points; grading remains the instructor's decision.",
             "", "| Requirement | Evidence / status |", "|---|---|"]
    rows = [
        ("Planning (separately graded, 4 points in supplied assignment)", "planning.md: signals, exact math, labels, appeals/edge cases, Architecture and AI Tool Plan; chronology verified below"),
        ("Submission endpoint", "provenance_guard/app.py; tests/test_api.py; saved response artifacts"),
        ("At least two distinct signals", "Groq semantic, stylometry and lexical repetition modules; independent signal tests"),
        ("Confidence and uncertainty", "ensemble.py and test_ensemble.py; inclusive thresholds, low evidence and disagreement tests; uncalibrated status explicit"),
        ("Three transparency labels", "Exact strings present in planning.md, README and labels.py; three endpoint fixture branches exercised"),
        ("Appeals", "Transactional store.appeal; creator match, unknown/duplicate, race and rollback tests; real appeal audit record"),
        ("Rate limiting", "Explicit memory storage; 10/minute and 100/day; real localhost HTTP 201×10 then 429×2"),
        ("Structured audit log", "artifacts/audit_sample.json: at least three real events including appeal, original scores retained"),
        ("Two observed submissions with high/lower confidence", live_status + "; controlled examples are separately labeled and do not substitute for live evidence"),
        ("README", "Architecture, setup, APIs, signals/math, exact labels, actual evidence, limitations, reflection, AI usage, manual video placeholder"),
        ("Stretch 1: ensemble", "Three signals with 50/30/20 weights and independent diagnostics"),
        ("Stretch 2: provenance certificate", "Expiring one-use challenge + registered token, persistent certificate and content display; verifies secret control ONLY, not humanity/authorship"),
        ("Stretch 3: dashboard", "Real SQLite attribution/appeal/confidence/uncertainty metrics; tests/test_analytics.py"),
        ("Stretch 4: second modality", "Structured metadata explicitly accepted by assignment; separate validation/consistency path, tests/test_metadata.py"),
        ("GitHub repository link", "MANUAL: local Git repository only; no remote creation or push authorized"),
        ("Portfolio video", "MANUAL: not recorded, as instructed by project owner"),
        ("Course submission", "MANUAL: not performed"),
    ]
    lines += [f"| {requirement} | {status} |" for requirement, status in rows]
    lines += ["", "## Automated repository checks", "", "| Check | Result |", "|---|---|"]
    lines += [f"| {label} | {'PASS' if passed else 'FAIL'} |" for label, passed in checks]
    lines += ["", f"Saved test result: **{total} tests, {failures} failures/errors, {skipped} skipped**. "
              "See pytest-results.xml. All tests are offline; no live success is inferred from mocks.",
              "", "## Planning chronology", "", f"Initial planning-only commit: `{commits[0][:7]}`.",
              "", "| Stretch | Planning commit | First implementation | Ordering |", "|---|---|---|---|"]
    lines += chronology
    lines += ["", "## Commit history at snapshot", "", "```text"]
    lines += [f"{commit[:7]} {subjects[commit]}" for commit in commits]
    lines += ["```", "", "## Verification limitations and remaining tasks", "",
              "- Scout live attempt returned HTTP 404 model_not_found; sanitized evidence is committed. "
              "Alternate model availability is distinct from permission to use it.",
              "- " + live_status + ".",
              "- Local token control is not a verified-human credential; the scope is disclosed, not fabricated.",
              "- No empirical accuracy/calibration claims, verified human corpus, public deployment or human code-review claims.",
              "- GitHub Actions is supplied but not claimed to have run remotely.",
              "- Owner must review, record video, create/push GitHub repository when authorized and submit course links.",
              "", "## Working tree inspection", "", "Tracked/staged changes immediately before this report was written:",
              "```text", git("status", "--short") or "clean", "```", "",
              "Final delivery checks run after committing this report verify a clean working tree. "
              "Private ignored files remain outside Git by design."]
    (ROOT / "artifacts" / "repository_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps({"checks": len(checks), "passed": sum(passed for _, passed in checks),
                      "tests": total, "live_evidence": live_status, "secret_scan_passed": not secret_hits}))
    if not all(passed for _, passed in checks):
        raise SystemExit("Repository check failed; see audit report (no secrets printed).")


if __name__ == "__main__":
    main()
