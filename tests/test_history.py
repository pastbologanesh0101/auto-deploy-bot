import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from history import DeploymentHistory  # noqa: E402


class TestDeploymentHistory(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmpdir.name, "history.db")
        self.history = DeploymentHistory(self.db_path)

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_record_and_retrieve_success(self):
        self.history.record("webhook", "abc123", "def456", True, output="ok")
        rows = self.history.recent()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["success"], 1)
        self.assertEqual(rows[0]["rolled_back"], 0)
        self.assertEqual(rows[0]["commit_before"], "abc123")
        self.assertEqual(rows[0]["commit_after"], "def456")

    def test_record_and_retrieve_failure_with_rollback(self):
        self.history.record("poll", "abc123", "def456", False, output="boom", rolled_back=True)
        rows = self.history.recent()
        self.assertEqual(rows[0]["success"], 0)
        self.assertEqual(rows[0]["rolled_back"], 1)

    def test_recent_limit_and_order(self):
        for i in range(5):
            self.history.record("webhook", "c{}".format(i), "c{}".format(i + 1), True)
        rows = self.history.recent(limit=3)
        self.assertEqual(len(rows), 3)
        # most recent first
        self.assertEqual(rows[0]["commit_before"], "c4")

    def test_history_persists_across_instances(self):
        self.history.record("webhook", "a", "b", True)
        reopened = DeploymentHistory(self.db_path)
        rows = reopened.recent()
        self.assertEqual(len(rows), 1)


if __name__ == "__main__":
    unittest.main()
