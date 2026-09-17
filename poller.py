"""Polling mode: check a local git repo for new commits on a schedule.

This is an alternative trigger to the webhook receiver, for cases where
there's no publicly reachable webhook endpoint.
"""
import time

from deploy import run_git


def get_local_head(repo_dir):
    return run_git(["rev-parse", "HEAD"], repo_dir).stdout.strip()


def get_remote_head(repo_dir, branch):
    run_git(["fetch", "origin", branch], repo_dir)
    return run_git(["rev-parse", "origin/{}".format(branch)], repo_dir).stdout.strip()


def has_new_commit(repo_dir, branch):
    """Return (new_commit_available, local_head, remote_head)."""
    local = get_local_head(repo_dir)
    remote = get_remote_head(repo_dir, branch)
    return local != remote, local, remote


class Poller:
    def __init__(self, config, deployer):
        self.config = config
        self.deployer = deployer

    def poll_once(self):
        """Check once for a new commit; deploy if one is found.

        Returns True if a deployment was triggered and succeeded, False
        otherwise (including when there was nothing new to deploy).
        """
        new_commit, _local, _remote = has_new_commit(
            self.config.target_repo_dir, self.config.target_branch
        )
        if new_commit:
            return self.deployer.deploy(trigger_source="poll")
        return False

    def run_forever(self):  # pragma: no cover - real long-running loop
        while True:
            self.poll_once()
            time.sleep(self.config.poll_interval_seconds)
