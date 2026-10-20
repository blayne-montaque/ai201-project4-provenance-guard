"""Independent live check; writes only sanitized service evidence, never keys."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from groq import APIError, Groq

from provenance_guard.config import ALTERNATE_MODEL, SCOUT_MODEL, settings
from provenance_guard.groq_signal import assess_semantic

SAMPLE = (
    "I found the blue notebook under a kitchen chair this morning. Its cover was bent "
    "where the dog had tried to carry it, and three pages smelled faintly of soup. "
    "My sister said she had been looking for it since Tuesday. I had no idea why she "
    "needed a list of old bus routes, but I put it beside her shoes. Later she called "
    "to tell me the notes were for a story about our grandfather, who drove the night "
    "bus for twenty years and never learned to like the radio."
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", choices=[SCOUT_MODEL, ALTERNATE_MODEL], default=SCOUT_MODEL)
    parser.add_argument("--output", default="artifacts/groq_smoke_scout.json")
    args = parser.parse_args()
    config = settings()
    config["GROQ_MODEL"] = args.model
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "mode": "live_api_attempt",
              "sample_source": "Codex-authored synthetic prose; not verified human text",
              "model": args.model, "assessment": assess_semantic(SAMPLE, config).public()}
    if config.get("GROQ_API_KEY"):
        try:
            with Groq(api_key=config["GROQ_API_KEY"], timeout=20, max_retries=0) as client:
                ids = {model.id for model in client.models.list().data}
            record["availability_check"] = {SCOUT_MODEL: SCOUT_MODEL in ids,
                                             ALTERNATE_MODEL: ALTERNATE_MODEL in ids}
        except APIError as exc:
            record["availability_check"] = {"error_type": type(exc).__name__,
                                             "http_status": getattr(exc, "status_code", None)}
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
