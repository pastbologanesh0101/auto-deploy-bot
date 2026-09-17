"""Core deployment logic: git pull, post-pull command, restart, rollback."""
import subprocess
import time


def run_git(args, cwd):
    return subprocess.run(["git"] + args, cwd=cwd, capture_output=True, text=True)


def get_head(repo_dir):
    result = run_git(["rev-parse", "HEAD"], repo_dir)
    return result.stdout.strip()


class Deployer:
    def __init__(self, config, process_manager, history):
        self.config = config
        self.process_manager = process_manager
        self.history = history

    def deploy(self, trigger_source="webhook"):
        """Run a full deployment cycle.

        Steps: git pull -> post-pull command -> restart target process.
        If the post-pull command fails, or the restart fails, the repo is
        rolled back to the commit it was on before the pull, and the
        attempt is recorded as a failed (rolled-back) deployment.
        """
        repo_dir = self.config.target_repo_dir
        output_lines = []
        commit_before = get_head(repo_dir)

        pull_result = run_git(["pull", "origin", self.config.target_branch], repo_dir)
        output_lines.append("git pull:\n" + pull_result.stdout + pull_result.stderr)
        if pull_result.returncode != 0:
            self.history.record(
                trigger_source,
                commit_before,
                commit_before,
                False,
                "\n".join(output_lines),
                rolled_back=False,
            )
            return False

        commit_after = get_head(repo_dir)

        if self.config.post_pull_command:
            post_result = subprocess.run(
                self.config.post_pull_command,
                shell=True,
                cwd=repo_dir,
                capture_output=True,
                text=True,
            )
            output_lines.append(
                "post-pull command:\n" + post_result.stdout + post_result.stderr
            )
            if post_result.returncode != 0:
                self._rollback(repo_dir, commit_before)
                self.history.record(
                    trigger_source,
                    commit_before,
                    commit_after,
                    False,
                    "\n".join(output_lines),
                    rolled_back=True,
                )
                return False

        restart_ok = self._restart()
        output_lines.append("restart: {}".format("ok" if restart_ok else "failed"))
        if not restart_ok:
            self._rollback(repo_dir, commit_before)
            self.history.record(
                trigger_source,
                commit_before,
                commit_after,
                False,
                "\n".join(output_lines),
                rolled_back=True,
            )
            return False

        self.history.record(
            trigger_source,
            commit_before,
            commit_after,
            True,
            "\n".join(output_lines),
            rolled_back=False,
        )
        return True

    def _rollback(self, repo_dir, commit_before):
        run_git(["reset", "--hard", commit_before], repo_dir)

    def _restart(self):
        if not self.config.restart_command:
            return True
        self.process_manager.stop()
        self.process_manager.start(self.config.restart_command)
        # Give the process a brief moment to either settle in or exit on
        # its own (e.g. a misconfigured/short-lived restart command).
        time.sleep(0.2)
        return self.process_manager.is_running()
