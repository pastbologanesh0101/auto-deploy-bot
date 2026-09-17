import hashlib
import hmac
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from config import Config  # noqa: E402

SECRET = "test-secret"


def sign(secret, body):
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return "sha256=" + digest


class TestWebhook(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        config = Config(
            webhook_secret=SECRET,
            target_repo_dir=self.tmpdir.name,
            target_branch="main",
            post_pull_command="",
            restart_command="",
            pid_file=os.path.join(self.tmpdir.name, "app.pid"),
            history_db=os.path.join(self.tmpdir.name, "history.db"),
        )
        self.app = create_app(config)
        # These tests only exercise webhook routing/signature verification;
        # deployment mechanics are covered thoroughly in test_deploy.py.
        self.app.extensions["deployer"].deploy = lambda trigger_source="webhook": True
        self.client = self.app.test_client()

    def tearDown(self):
        self.tmpdir.cleanup()

    def _push_payload(self, ref="refs/heads/main"):
        return json.dumps({"ref": ref}).encode()

    def test_valid_signature_accepted_and_deploys(self):
        body = self._push_payload()
        headers = {
            "X-Hub-Signature-256": sign(SECRET, body),
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        }
        resp = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "deployed")

    def test_invalid_signature_rejected(self):
        body = self._push_payload()
        headers = {
            "X-Hub-Signature-256": "sha256=" + "0" * 64,
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        }
        resp = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 401)

    def test_missing_signature_rejected(self):
        body = self._push_payload()
        resp = self.client.post(
            "/webhook", data=body, headers={"Content-Type": "application/json"}
        )
        self.assertEqual(resp.status_code, 401)

    def test_push_to_non_configured_branch_ignored(self):
        body = self._push_payload(ref="refs/heads/develop")
        headers = {
            "X-Hub-Signature-256": sign(SECRET, body),
            "X-GitHub-Event": "push",
            "Content-Type": "application/json",
        }
        resp = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ignored")

    def test_non_push_event_ignored(self):
        body = self._push_payload()
        headers = {
            "X-Hub-Signature-256": sign(SECRET, body),
            "X-GitHub-Event": "ping",
            "Content-Type": "application/json",
        }
        resp = self.client.post("/webhook", data=body, headers=headers)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["status"], "ignored")

    def test_health_endpoint(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
