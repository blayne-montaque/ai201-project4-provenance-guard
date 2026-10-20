"""Local proof of token control. This is deliberately not identity verification."""
import hashlib
import hmac
import json
import secrets
import time
from uuid import uuid4

from .errors import APIError
from .storage import utcnow

ITERATIONS = 200_000
METHOD = "one_time_challenge_and_registered_token"
SCOPE = "Verifies control of a registered token only; not humanity, identity, or authorship."


def verifier(token, salt):
    return hashlib.pbkdf2_hmac("sha256", token.encode("utf-8"), bytes.fromhex(salt), ITERATIONS).hex()


class Verification:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock
        with store.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS verification_creators (
                    creator_id TEXT PRIMARY KEY, salt TEXT NOT NULL, verifier TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS challenges (
                    challenge_id TEXT PRIMARY KEY,
                    creator_id TEXT NOT NULL REFERENCES verification_creators(creator_id),
                    nonce_hash TEXT NOT NULL, expires_at REAL NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0, consumed INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE IF NOT EXISTS certificates (
                    certificate_id TEXT PRIMARY KEY,
                    creator_id TEXT UNIQUE NOT NULL REFERENCES verification_creators(creator_id),
                    certificate TEXT NOT NULL
                );
            """)

    def register(self, creator_id):
        token, salt = secrets.token_urlsafe(32), secrets.token_hex(16)
        digest = verifier(token, salt)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT 1 FROM verification_creators WHERE creator_id=?", (creator_id,)).fetchone():
                raise APIError("creator_already_registered", "That creator ID is already registered.", 409)
            db.execute("INSERT INTO verification_creators VALUES(?,?,?)", (creator_id, salt, digest))
        return {"creator_id": creator_id, "verification_token": token,
                "notice": "Save this token now; it is returned only once. " + SCOPE}

    def challenge(self, creator_id):
        challenge_id, nonce = str(uuid4()), secrets.token_urlsafe(32)
        expires_at = self.clock() + 300
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            if not db.execute("SELECT 1 FROM verification_creators WHERE creator_id=?", (creator_id,)).fetchone():
                raise APIError("creator_not_registered", "Register a verification token first.", 404)
            db.execute("UPDATE challenges SET consumed=1 WHERE creator_id=? AND consumed=0", (creator_id,))
            db.execute("INSERT INTO challenges(challenge_id,creator_id,nonce_hash,expires_at) VALUES(?,?,?,?)",
                       (challenge_id, creator_id, hashlib.sha256(nonce.encode()).hexdigest(), expires_at))
        return {"challenge_id": challenge_id, "creator_id": creator_id, "nonce": nonce,
                "expires_at_unix": expires_at, "expires_in_seconds": 300, "method": METHOD}

    def verify(self, creator_id, challenge_id, nonce, token):
        failure, certificate = None, None
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            challenge = db.execute("SELECT * FROM challenges WHERE challenge_id=? AND creator_id=?",
                                   (challenge_id, creator_id)).fetchone()
            if challenge is None:
                raise APIError("challenge_not_found", "No challenge matches that creator and ID.", 404)
            if challenge["consumed"]:
                raise APIError("challenge_used", "This challenge has already been consumed or replaced.", 409)
            if challenge["expires_at"] <= self.clock():
                raise APIError("challenge_expired", "Request a new challenge.", 410)
            if challenge["attempts"] >= 5:
                raise APIError("challenge_locked", "Too many failed attempts; request a new challenge.", 429)
            registered = db.execute("SELECT * FROM verification_creators WHERE creator_id=?", (creator_id,)).fetchone()
            token_ok = hmac.compare_digest(verifier(token, registered["salt"]), registered["verifier"])
            nonce_ok = hmac.compare_digest(hashlib.sha256(nonce.encode()).hexdigest(), challenge["nonce_hash"])
            if not (token_ok and nonce_ok):
                db.execute("UPDATE challenges SET attempts=attempts+1 WHERE challenge_id=?", (challenge_id,))
                failure = APIError("verification_failed", "The challenge response could not be verified.", 403)
            else:
                db.execute("UPDATE challenges SET consumed=1 WHERE challenge_id=?", (challenge_id,))
                existing = db.execute("SELECT certificate FROM certificates WHERE creator_id=?", (creator_id,)).fetchone()
                if existing:
                    certificate = json.loads(existing["certificate"])
                else:
                    certificate = {"certificate_id": str(uuid4()), "creator_id": creator_id,
                                   "verification_method": METHOD, "issued_at": utcnow(),
                                   "verification_status": "verified_secret_control",
                                   "display_label": "Verified secret control (demo)", "scope": SCOPE}
                    db.execute("INSERT INTO certificates VALUES(?,?,?)",
                               (certificate["certificate_id"], creator_id, json.dumps(certificate)))
                    self.store._event(db, "certificate_issued", None, certificate)
        # Failed attempts must commit before the HTTP error is raised.
        if failure:
            raise failure
        return certificate

    def for_creator(self, creator_id):
        with self.store.connection() as db:
            row = db.execute("SELECT certificate FROM certificates WHERE creator_id=?", (creator_id,)).fetchone()
        return json.loads(row["certificate"]) if row else None

    def get(self, certificate_id):
        with self.store.connection() as db:
            row = db.execute("SELECT certificate FROM certificates WHERE certificate_id=?", (certificate_id,)).fetchone()
        if not row:
            raise APIError("certificate_not_found", "No certificate exists with that ID.", 404)
        return {**json.loads(row["certificate"]), "valid": True}

