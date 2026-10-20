"""Capture real local API executions; mode clearly distinguishes live from fixtures.

No private creator content is used. Each run creates a NEW ignored SQLite DB.
Exported evidence includes only bundled public samples, not registration secrets.
"""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from provenance_guard import create_app
from provenance_guard.config import ROOT
from provenance_guard.signals import Signal
from provenance_guard.storage import utcnow


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def capture(mode, output):
    run_id = str(uuid4())
    config = {"DATABASE": str(ROOT / "instance" / f"demo-{mode}-{run_id}.sqlite3")}
    fixtures = {"high_ai": .95, "lower_uncertain": .65, "high_human": .05}
    if mode == "offline":
        config["GROQ_API_KEY"] = ""  # Real degraded behavior; no invented semantic score.
    elif mode == "controlled":
        for key, name in [("SEMANTIC_ANALYZER", "groq"), ("STYLOMETRIC_ANALYZER", "stylometry"),
                          ("REPETITION_ANALYZER", "repetition")]:
            config[key] = lambda text, name=name: Signal(name, fixtures[text.split()[0]],
                                                        diagnostics={"source": "controlled_test_fixture"})
    app = create_app(config)
    output.mkdir(parents=True, exist_ok=True)
    samples = json.loads((ROOT / "examples" / "submissions.json").read_text(encoding="utf-8"))
    if mode == "controlled":
        samples = [{"name": name, "source": "Controlled signal fixture; NOT a live model classification.",
                    "text": name + " " + ("The writer opened a notebook and studied the garden where rain "
                                              "had left small pools beneath the old apple trees. " * 5)}
                   for name in fixtures]
    observations = {"captured_at": utcnow(), "run_id": run_id, "mode": mode,
                    "transport": "Flask test client exercising real routes and SQLite",
                    "model": app.config["GROQ_MODEL"], "submissions": []}
    with app.test_client() as client:
        for sample in samples:
            response = client.post("/submit", json={"creator_id": "demo-writer", "text": sample["text"]})
            assert response.status_code == 201, response.status_code
            observations["submissions"].append({"name": sample["name"], "source": sample["source"],
                                                 "text": sample["text"], "http_status": response.status_code,
                                                 "response": response.json})
        target = observations["submissions"][0]["response"]["content_id"]
        appeal = client.post("/appeal", json={"content_id": target, "creator_id": "demo-writer",
                                              "creator_reasoning": "Demonstration appeal: please review the original draft and its context."})
        assert appeal.status_code == 201
        observations["appeal"] = {"http_status": appeal.status_code, "response": appeal.json}
        observations["post_appeal_content"] = client.get("/content/" + target).json
        registration = client.post("/creators/register", json={"creator_id": "demo-writer"}).json
        challenge = client.post("/verification/challenge", json={"creator_id": "demo-writer"}).json
        certificate = client.post("/verification/verify", json={
            "creator_id": "demo-writer", "challenge_id": challenge["challenge_id"],
            "nonce": challenge["nonce"], "verification_token": registration["verification_token"]})
        assert certificate.status_code == 201
        observations["certificate"] = certificate.json  # Never export token/nonce.
        observations["credential_on_content"] = client.get("/content/" + target).json["certificate"]
        metadata = client.post("/submit", json=json.loads((ROOT / "examples" / "metadata.json").read_text()))
        assert metadata.status_code == 201
        observations["metadata"] = metadata.json
        observations["analytics"] = client.get("/analytics").json
        events = client.get("/log?limit=200").json["entries"]
        write_json(output / "audit_log.json", {"mode": mode, "entries": events})
        (output / "dashboard.html").write_text(client.get("/dashboard").get_data(as_text=True), encoding="utf-8")
    write_json(output / "observations.json", observations)
    print(json.dumps({"mode": mode, "output": str(output), "submissions": [
        {"name": item["name"], "attribution": item["response"]["attribution"],
         "score": item["response"]["ai_likelihood_score"], "confidence": item["response"]["confidence"]}
        for item in observations["submissions"]]}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["offline", "controlled", "live"], default="offline")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    capture(args.mode, args.output or ROOT / "artifacts" / f"demo_{args.mode}")


if __name__ == "__main__":
    main()
