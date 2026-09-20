# Changelog

## [0.1.0] - Initial release

The initial release of Auto Deployment Bot: a self-contained auto-deploy
bot for a local git repo and process, requiring no cloud account, systemd,
or CI runner.

Included:

- `app.py` — Flask webhook receiver (`POST /webhook`, `GET /health`) that
  verifies GitHub-style `X-Hub-Signature-256` HMAC-SHA256 signatures with a
  constant-time comparison, filters events to `push` on the configured
  branch, and triggers a deployment.
- `poller.py` — an alternative, no-public-endpoint trigger that compares
  local `HEAD` against `origin/<branch>` on a schedule.
- `deploy.py` — the shared deployment routine: `git pull` → optional
  post-pull command → restart → automatic rollback (`git reset --hard`) to
  the pre-pull commit if the post-pull command or restart fails.
- `process_manager.py` — a PID-file-based process manager (start/stop/
  is_running) standing in for a real service manager, so restarts are
  testable against ordinary subprocesses.
- `history.py` — a SQLite-backed deployment history (trigger source,
  commit before/after, success, rollback flag, captured output, timestamp).
- `status.py` — a CLI (`-n`/`--limit`, `-v`/`--verbose`) to inspect recent
  deployment history.
- `config.py` — typed `Config` dataclass, loadable from environment
  variables (`Config.from_env()`) or a `config.json` (`Config.from_file()`).
- A test suite (26 tests) using real temporary git repositories and real
  short-lived subprocesses for every test — nothing mocked at the git or
  process level — covering webhook signature handling, end-to-end deploys,
  rollback on failure, history recording, process-manager lifecycle, and
  polling-mode commit detection.
- CI (`.github/workflows/tests.yml`) running the suite on Python 3.11 and
  3.12, plus an MIT license.
