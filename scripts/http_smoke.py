"""Real localhost HTTP startup, shared limit and 429 evidence without Groq calls."""
import json
import threading
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4

from werkzeug.serving import WSGIRequestHandler, make_server

from provenance_guard import create_app
from provenance_guard.config import ROOT
from provenance_guard.storage import utcnow


class QuietHandler(WSGIRequestHandler):
    def log(self, type, message, *args):
        pass


def main():
    app = create_app({"DATABASE": ROOT / "instance" / f"http-{uuid4()}.sqlite3", "GROQ_API_KEY": "",
                      "SUBMISSION_LIMITS": "10 per minute;100 per day"})
    server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    record = {"timestamp": utcnow(), "transport": "real localhost HTTP / Werkzeug WSGI server",
              "semantic_mode": "missing-key degraded analysis; no mocked scores or live model calls",
              "limits": app.config["SUBMISSION_LIMITS"]}
    try:
        with urlopen(base + "/health", timeout=5) as response:
            record["health"] = {"http_status": response.status, "body": json.load(response)}
        statuses = []
        for _ in range(12):
            request = Request(base + "/submit", data=json.dumps({"creator_id": "rate-demo",
                "text": "This is a public rate-limit demonstration submission."}).encode(),
                headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urlopen(request, timeout=10) as response:
                    statuses.append(response.status)
            except HTTPError as response:
                statuses.append(response.code)
                record["last_error"] = json.load(response)
                record["retry_after"] = response.headers.get("Retry-After")
        record["statuses"] = statuses
        assert statuses == [201] * 10 + [429, 429]
        with urlopen(base + "/log", timeout=5) as response:
            record["persisted_submissions"] = len(json.load(response)["entries"])
        with urlopen(base + "/dashboard", timeout=5) as response:
            record["dashboard_http_status"] = response.status
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    output = ROOT / "artifacts" / "http_smoke.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
