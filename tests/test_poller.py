import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import Config  # noqa: E402
from deploy import Deployer, get_head  # noqa: E402
from helpers import commit_new_change, make_repo_pair  # noqa: E402
from history import DeploymentHistory  # noqa: E402
from poller import Poller, has_new_commit  # noqa: E402
from process_manager import ProcessManager  # noqa: E402


class TestPoller(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.remote_dir, self.target_dir, self.seed_dir = make_repo_pair(self.tmpdir.name)
        self.config = Config(
            webhook_secret="x",
            target_repo_dir=self.target_dir,
            target_branch="main",
            post_pull_command="",
            restart_command="",
            pid_file=os.path.join(self.tmpdir.name, "app.pid"),
            history_db=os.path.join(self.tmpdir.name, "history.db"),
        )
        self.pm = ProcessManager(self.config.pid_file)
        self.history = DeploymentHistory(self.config.history_db)
        self.deployer = Deployer(self.config, self.pm, self.history)
        self.poller = Poller(self.config, self.deployer)

    def tearDown(self):
        if self.pm.is_running():
            self.pm.stop()
        self.tmpdir.cleanup()

    def test_no_new_commit_detected_when_up_to_date(self):
        new_commit, local, remote = has_new_commit(self.target_dir, "main")
        self.assertFalse(new_commit)
        self.assertEqual(local, remote)

    def test_new_commit_detected_after_push(self):
        new_head = commit_new_change(self.seed_dir, self.remote_dir)
        new_commit, local, remote = has_new_commit(self.target_dir, "main")
        self.assertTrue(new_commit)
        self.assertEqual(remote, new_head)
        self.assertNotEqual(local, new_head)

    def test_poll_once_triggers_deploy_on_new_commit(self):
        new_head = commit_new_change(self.seed_dir, self.remote_dir)
        result = self.poller.poll_once()
        self.assertTrue(result)
        self.assertEqual(get_head(self.target_dir), new_head)

    def test_poll_once_does_nothing_when_up_to_date(self):
        result = self.poller.poll_once()
        self.assertFalse(result)
        rows = self.history.recent()
        self.assertEqual(len(rows), 0)


if __name__ == "__main__":
    unittest.main()
