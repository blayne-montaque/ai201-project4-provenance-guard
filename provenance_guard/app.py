import sqlite3

from flask import Flask, jsonify, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.exceptions import HTTPException

from .config import settings
from .errors import APIError
from .ensemble import combine
from .groq_signal import assess_semantic
from .repetition import assess_repetition
from .storage import Store
from .stylometry import assess_stylometry
from .validation import creator, fields, json_object, string


def create_app(config=None):
    app = Flask(__name__)
    app.config.update(settings())
    if config:
        app.config.update(config)
    store = Store(app.config["DATABASE"])
    app.extensions["store"] = store
    semantic = app.config.get("SEMANTIC_ANALYZER") or (lambda text: assess_semantic(text, app.config))
    stylometry = app.config.get("STYLOMETRIC_ANALYZER") or assess_stylometry
    repetition = app.config.get("REPETITION_ANALYZER") or assess_repetition
    limiter = Limiter(get_remote_address, app=app, default_limits=[],
                      storage_uri=app.config["RATELIMIT_STORAGE_URI"],
                      headers_enabled=app.config["RATELIMIT_HEADERS_ENABLED"])
    # Keep a strong reference even when disabled: decorated routes use weakrefs.
    app.extensions["submission_limiter"] = limiter

    @app.errorhandler(APIError)
    def api_error(exc):
        return jsonify(error={"code": exc.code, "message": exc.message}), exc.status

    @app.errorhandler(HTTPException)
    def http_error(exc):
        code = "rate_limit_exceeded" if exc.code == 429 else f"http_{exc.code}"
        return jsonify(error={"code": code, "message": exc.name}), exc.code

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
    @limiter.limit(lambda: app.config["SUBMISSION_LIMITS"])
    def submit():
        data = json_object()
        fields(data, ("text", "creator_id"), ("content_type",))
        if data.get("content_type", "text") != "text":
            raise APIError("invalid_content_type", "This endpoint currently accepts text.")
        creator_id = creator(data)
        text = string(data, "text", app.config["MAX_TEXT_LENGTH"])
        assessment = combine(text, {"groq": semantic(text), "stylometry": stylometry(text),
                                    "repetition": repetition(text)})
        return jsonify(store.submit(creator_id, text, assessment)), 201

    @app.post("/appeal")
    @limiter.limit("20 per minute")
    def appeal():
        data = json_object()
        fields(data, ("content_id", "creator_id", "creator_reasoning"))
        content_id = string(data, "content_id", 80)
        creator_id = creator(data)
        reasoning = string(data, "creator_reasoning", 2000)
        return jsonify(store.appeal(content_id, creator_id, reasoning)), 201

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

