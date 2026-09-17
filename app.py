"""Flask webhook receiver for Auto Deployment Bot.

Verifies GitHub-style webhook signatures (HMAC-SHA256, `X-Hub-Signature-256`)
and triggers a deployment on a valid push event to the configured branch.
"""
import hashlib
import hmac

from flask import Flask, jsonify, request

from config import Config
from deploy import Deployer
from history import DeploymentHistory
from process_manager import ProcessManager


def verify_signature(secret, payload_body, signature_header):
    """Verify a GitHub-style `X-Hub-Signature-256` header.

    GitHub computes `sha256=<hex hmac>` over the raw request body using the
    shared secret. We recompute it the same way and compare with a
    constant-time comparison to avoid timing attacks.
    """
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
    provided = signature_header.split("=", 1)[1]
    return hmac.compare_digest(expected, provided)


def create_app(config=None):
    config = config or Config.from_env()
    app = Flask(__name__)
    app.config["APP_CONFIG"] = config

    process_manager = ProcessManager(config.pid_file)
    history = DeploymentHistory(config.history_db)
    deployer = Deployer(config, process_manager, history)

    if not hasattr(app, "extensions"):
        app.extensions = {}
    app.extensions["deployer"] = deployer
    app.extensions["history"] = history
    app.extensions["process_manager"] = process_manager

    @app.route("/webhook", methods=["POST"])
    def webhook():
        signature = request.headers.get("X-Hub-Signature-256", "")
        if not verify_signature(config.webhook_secret, request.data, signature):
            return jsonify({"error": "invalid signature"}), 401

        event_type = request.headers.get("X-GitHub-Event", "push")
        payload = request.get_json(silent=True) or {}

        if event_type != "push":
            return jsonify({"status": "ignored", "reason": "not a push event"}), 200

        ref = payload.get("ref", "")
        expected_ref = "refs/heads/{}".format(config.target_branch)
        if ref != expected_ref:
            return (
                jsonify({"status": "ignored", "reason": "branch mismatch ({})".format(ref)}),
                200,
            )

        success = app.extensions["deployer"].deploy(trigger_source="webhook")
        return jsonify({"status": "deployed" if success else "failed"}), 200

    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({"status": "ok"}), 200

    return app


if __name__ == "__main__":  # pragma: no cover
    app = create_app()
    app.run(host="0.0.0.0", port=5000)
