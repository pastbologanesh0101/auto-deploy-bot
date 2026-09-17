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
from process_manager import ProcessManager  # noqa: E402


class TestDeployer(unittest.TestCase):
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

    def tearDown(self):
        if self.pm.is_running():
            self.pm.stop()
        self.tmpdir.cleanup()

    def test_deploy_pulls_new_commit_successfully(self):
        new_head = commit_new_change(self.seed_dir, self.remote_dir)
        before = get_head(self.target_dir)
        self.assertNotEqual(before, new_head)

        success = self.deployer.deploy(trigger_source="test")

        self.assertTrue(success)
        self.assertEqual(get_head(self.target_dir), new_head)

    def test_deploy_records_history_on_success(self):
        commit_new_change(self.seed_dir, self.remote_dir)
        self.deployer.deploy(trigger_source="webhook")

        rows = self.history.recent(limit=1)
        self.assertEqual(rows[0]["trigger_source"], "webhook")
        self.assertEqual(rows[0]["success"], 1)
        self.assertEqual(rows[0]["rolled_back"], 0)

    def test_deploy_rolls_back_on_failing_post_pull_command(self):
        before = get_head(self.target_dir)
        new_head = commit_new_change(self.seed_dir, self.remote_dir)
        self.config.post_pull_command = "exit 1"

        success = self.deployer.deploy(trigger_source="test")

        self.assertFalse(success)
        current_head = get_head(self.target_dir)
        self.assertEqual(current_head, before)
        self.assertNotEqual(current_head, new_head)

    def test_failed_post_pull_records_failure_and_rollback_in_history(self):
        commit_new_change(self.seed_dir, self.remote_dir)
        self.config.post_pull_command = "exit 1"

        self.deployer.deploy(trigger_source="test")

        rows = self.history.recent(limit=1)
        self.assertEqual(rows[0]["success"], 0)
        self.assertEqual(rows[0]["rolled_back"], 1)

    def test_deploy_rolls_back_on_restart_failure(self):
        commit_new_change(self.seed_dir, self.remote_dir)
        before = get_head(self.target_dir)
        # "true" exits immediately, so is_running() will be False right
        # after start -- simulating a restart command that fails to keep
        # the target process alive.
        self.config.restart_command = "true"

        success = self.deployer.deploy(trigger_source="test")

        self.assertFalse(success)
        self.assertEqual(get_head(self.target_dir), before)
        rows = self.history.recent(limit=1)
        self.assertEqual(rows[0]["rolled_back"], 1)

    def test_deploy_with_no_new_commits_still_succeeds(self):
        # Nothing new pushed -- pull is a no-op, deploy should still report
        # success since nothing failed.
        success = self.deployer.deploy(trigger_source="test")
        self.assertTrue(success)


if __name__ == "__main__":
    unittest.main()
