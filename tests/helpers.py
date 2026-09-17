"""Shared helpers for building real, throwaway git repos in tests."""
import os
import subprocess


def run(cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            "Command failed: {}\nstdout: {}\nstderr: {}".format(
                cmd, result.stdout, result.stderr
            )
        )
    return result


def _configure_identity(repo_dir):
    run(["git", "config", "user.email", "test@example.com"], cwd=repo_dir)
    run(["git", "config", "user.name", "Test Bot"], cwd=repo_dir)


def make_repo_pair(tmp_root, branch="main"):
    """Build a bare 'remote' repo plus two working clones.

    - `seed_dir`: a clone used by the test to push new commits (simulates
      a developer pushing code).
    - `target_dir`: a clone that represents the deployment target, i.e.
      the directory the bot runs `git pull` in.

    Returns (remote_dir, target_dir, seed_dir), each with one initial
    commit already pushed and pulled.
    """
    remote_dir = os.path.join(tmp_root, "remote.git")
    target_dir = os.path.join(tmp_root, "target")
    seed_dir = os.path.join(tmp_root, "seed")

    run(["git", "init", "--bare", "-b", branch, remote_dir])

    run(["git", "init", "-b", branch, seed_dir])
    _configure_identity(seed_dir)
    with open(os.path.join(seed_dir, "file.txt"), "w") as f:
        f.write("v1\n")
    run(["git", "add", "."], cwd=seed_dir)
    run(["git", "commit", "-m", "initial commit"], cwd=seed_dir)
    run(["git", "remote", "add", "origin", remote_dir], cwd=seed_dir)
    run(["git", "push", "origin", branch], cwd=seed_dir)

    run(["git", "clone", remote_dir, target_dir])
    run(["git", "checkout", branch], cwd=target_dir)
    _configure_identity(target_dir)

    return remote_dir, target_dir, seed_dir


def commit_new_change(seed_dir, remote_dir, branch="main", content="v2\n", filename="file.txt"):
    """Push a new commit from `seed_dir` to `remote_dir`. Returns new HEAD hash."""
    with open(os.path.join(seed_dir, filename), "w") as f:
        f.write(content)
    run(["git", "add", "."], cwd=seed_dir)
    run(["git", "commit", "-m", "update"], cwd=seed_dir)
    run(["git", "push", "origin", branch], cwd=seed_dir)
    return run(["git", "rev-parse", "HEAD"], cwd=seed_dir).stdout.strip()
