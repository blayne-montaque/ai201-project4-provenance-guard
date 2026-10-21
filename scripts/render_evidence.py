"""Derive README evidence from saved responses; never invent IDs or scores."""
import json

from provenance_guard.config import ROOT


def load(mode):
    path = ROOT / "artifacts" / f"demo_{mode}" / "observations.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def main():
    offline, controlled, live = load("offline"), load("controlled"), load("live")
    parts = []
    if live:
        parts += [f"Live execution with `{live['model']}`, captured {live['captured_at']}.",
                  "These are observed API responses, not injected signal values. "
                  "Input authorship is described in the source file; samples are not an accuracy benchmark.",
                  "| Submission | Raw AI estimate | Decision confidence | Attribution |",
                  "|---|---:|---:|---|"]
        for item in live["submissions"]:
            record = item["response"]
            parts.append(f"| {item['name']} | {record['ai_likelihood_score']} | "
                         f"{record['confidence']:.6f} | {record['attribution']} |")
        parts += ["", "Full texts, diagnostics and responses: [live observations](artifacts/demo_live/observations.json)."]
        complete = [item for item in live["submissions"] if item["response"].get("analysis_status") == "complete"]
        if complete:
            high = max(complete, key=lambda item: item["response"]["confidence"])
            low = min(complete, key=lambda item: item["response"]["confidence"])
            parts += ["", f"The observed high/lower pair is **{high['name']} "
                      f"({high['response']['confidence']:.6f}, {high['response']['attribution']})** and "
                      f"**{low['name']} ({low['response']['confidence']:.6f}, {low['response']['attribution']})**. "
                      "Confidence supports the reported decision, not an authorship probability."]
            if all(item["response"]["attribution"] == "uncertain" for item in complete):
                parts += ["All live examples in this run remain uncertain. The high-confidence case is "
                          "**confident uncertainty**, not a high-confidence AI/human verdict. "
                          "No live directional classification is claimed, and no threshold was tuned "
                          "to manufacture one. The longer sample has adequate length but the semantic "
                          "signal remains uncertain; the short poem's limited evidence lowers confidence."]
    else:
        parts += ["**Live high/lower-confidence example requirement is pending.** "
                  "The prescribed model returned 404; no alternate-model approval has been recorded. "
                  "The values below must not be presented as successful live Groq classifications."]
    parts += ["", "Actual offline submissions exercised the real local signals, routes, SQLite and appeals "
              "with the API key deliberately absent. All six returned a null combined estimate and "
              "confidence 0, as specified for degraded analysis. Their local measurements still vary:",
              "", "| Submitted example | Stylometry | Repetition | Decision confidence |",
              "|---|---:|---:|---:|"]
    for item in offline["submissions"]:
        record = item["response"]
        parts.append(f"| {item['name']} | {record['signals']['stylometry']['score']:.6f} | "
                     f"{record['signals']['repetition']['score']:.6f} | {record['confidence']:.6f} |")
    parts += ["", "Full public texts and actual response objects: "
              "[offline observations](artifacts/demo_offline/observations.json). "
              "The assignment's four examples are all shorter than the 80-word sufficiency threshold; "
              "that conservative decision is preserved, not tuned away for a demonstration.",
              "", "Controlled endpoint executions use deliberately injected fixed scores to verify "
              "branch reachability. These are **test fixtures, not model results**:",
              "", "| Controlled submission | Raw estimate | Decision confidence | Attribution |",
              "|---|---:|---:|---|"]
    for item in controlled["submissions"]:
        record = item["response"]
        parts.append(f"| {item['name']} | {record['ai_likelihood_score']:.2f} | "
                     f"{record['confidence']:.2f} | {record['attribution']} |")
    parts += ["", "[Controlled response evidence](artifacts/demo_controlled/observations.json) "
              "includes its fixture provenance on every signal. It demonstrates high/lower "
              "decision support and all three exact labels, without claiming empirical detection quality."]
    mode = "live" if live else "offline"
    source = live or offline
    events = json.loads((ROOT / "artifacts" / f"demo_{mode}" / "audit_log.json").read_text(encoding="utf-8"))["entries"]
    submissions = sorted((e for e in events if e["event_type"] == "submission" and e["content_type"] == "text"),
                         key=lambda e: e["event_id"])
    appeal = next(e for e in events if e["event_type"] == "appeal")
    sample = submissions[:2] + [appeal]
    (ROOT / "artifacts" / "audit_sample.json").write_text(
        json.dumps({"mode": mode, "entries": sample}, indent=2) + "\n", encoding="utf-8")
    projection = [{key: event[key] for key in ("event_id", "event_type", "timestamp", "content_id",
                  "attribution", "ai_likelihood_score", "confidence", "status", "appeal_filed")}
                  | {"signal_scores": {name: signal["score"] for name, signal in event["signals"].items()}}
                  | ({"appeal_reasoning": event["appeal_reasoning"]} if "appeal_reasoning" in event else {})
                  for event in sample]
    parts += ["", f"Three **actual SQLite audit entries** from the `{mode}` run follow "
              "(a field projection for readability). "
              "[Full entries with diagnostics](artifacts/audit_sample.json) and "
              f"[complete run log](artifacts/demo_{mode}/audit_log.json) are committed. "
              "The third event is the appeal on the first submission; the first event remains classified.",
              "", "```json", json.dumps(projection, indent=2), "```", "",
              f"Observed appeal response: `{source['appeal']['http_status']}`. The content subsequently "
              f"returned `status: {source['post_appeal_content']['status']}`; its original scores were retained. "
              "The same run also issued a real local verification credential and submitted metadata, "
              "then rendered a dashboard from those records. Verification tokens/nonces are excluded "
              "from the evidence exports."]
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    start, end = "<!-- BEGIN GENERATED EVIDENCE -->", "<!-- END GENERATED EVIDENCE -->"
    before, tail = text.split(start, 1)
    _, after = tail.split(end, 1)
    readme.write_text(before + start + "\n" + "\n".join(parts) + "\n" + end + after, encoding="utf-8")
    print("README evidence regenerated from stored responses; audit sample exported.")


if __name__ == "__main__":
    main()
