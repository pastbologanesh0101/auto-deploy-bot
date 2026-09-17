"""Configuration for Auto Deployment Bot.

Config can be built explicitly (recommended for tests) or loaded from
environment variables / a JSON file for real deployments.
"""
import json
import os
from dataclasses import dataclass


@dataclass
class Config:
    webhook_secret: str = "changeme"
    target_repo_dir: str = "./target_repo"
    target_branch: str = "main"
    post_pull_command: str = ""
    restart_command: str = ""
    pid_file: str = "./deploy_target.pid"
    history_db: str = "./deployment_history.db"
    poll_interval_seconds: int = 60

    @classmethod
    def from_file(cls, path="config.json"):
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            return cls(**data)
        return cls()

    @classmethod
    def from_env(cls):
        c = cls()
        c.webhook_secret = os.environ.get("WEBHOOK_SECRET", c.webhook_secret)
        c.target_repo_dir = os.environ.get("TARGET_REPO_DIR", c.target_repo_dir)
        c.target_branch = os.environ.get("TARGET_BRANCH", c.target_branch)
        c.post_pull_command = os.environ.get("POST_PULL_COMMAND", c.post_pull_command)
        c.restart_command = os.environ.get("RESTART_COMMAND", c.restart_command)
        c.pid_file = os.environ.get("PID_FILE", c.pid_file)
        c.history_db = os.environ.get("HISTORY_DB", c.history_db)
        c.poll_interval_seconds = int(
            os.environ.get("POLL_INTERVAL_SECONDS", c.poll_interval_seconds)
        )
        return c
