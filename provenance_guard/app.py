import sqlite3

from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from .config import settings
from .errors import APIError
from .groq_signal import assess_semantic
from .storage import Store
from .validation import creator, fields, json_object, string


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(settings())
    if config:
        app.config.update(config)
    store = Store(app.config["DATABASE"])
    app.extensions["store"] = store
    semantic = app.config.get("SEMANTIC_ANALYZER") or (lambda text: assess_semantic(text, app.config))

    @app.errorhandler(APIError)
    def api_error(exc):
        return jsonify(error={"code": exc.code, "message": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        return jsonify(error={"code": f"http_{exc.code}", "message": exc.name}), exc.code

    @app.errorhandler(sqlite3.Error)
    def database_error(exc):
        return jsonify(error={"code": "storage_unavailable", "message": "Storage is temporarily unavailable."}), 503

    @app.after_request
    def response_headers(response):
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @app.get("/health")
    def health():
        return jsonify(status="ok", service="ai201-project4-provenance-guard")

    @app.post("/submit")
    def submit():
        data = json_object()
        fields(data, ("text", "creator_id"), ("content_type",))
        if data.get("content_type", "text") != "text":
            raise APIError("invalid_content_type", "This endpoint currently accepts text.")
        creator_id = creator(data)
        text = string(data, "text", app.config["MAX_TEXT_LENGTH"])
        signal = semantic(text)
        # Checkpoint A deliberately exposes a provisional, non-directional result.
        assessment = {"attribution": "uncertain", "ai_likelihood_score": signal.score,
                      "confidence": 0.0, "label": "Initial semantic assessment; ensemble pending.",
                      "signals": {"groq": signal.public()},
                      "uncertainty_reasons": ["checkpoint_a_ensemble_pending"]}
        return jsonify(store.submit(creator_id, text, assessment)), 201

    @app.get("/content/<content_id>")
    def get_content(content_id):
        return jsonify(store.get(content_id))

    @app.get("/log")
    def log():
        try:
            limit = int(request.args.get("limit", "50"))
            if not 1 <= limit <= 200:
                raise ValueError()
        except ValueError:
            raise APIError("invalid_limit", "limit must be an integer between 1 and 200.") from None
        return jsonify(entries=store.log(limit))

    return app

