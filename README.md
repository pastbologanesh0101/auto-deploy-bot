# Auto Deployment Bot

A small, fully self-contained "auto-deploy" bot for a **local** git repo and
process — no cloud account, no systemd, no CI runner required. It
demonstrates the complete auto-deploy pattern:

1. Detect that new code has landed on a branch (via a GitHub webhook, or by
   polling a local clone on a schedule).
2. `git pull` the target repo directory.
3. Run a configurable post-pull command (install deps, build, etc).
4. Restart a target process, tracked through a tiny PID-file-based process
   manager (no systemd/supervisor dependency).
5. Record every attempt (success, failure, rollback) to a local SQLite
   history you can inspect with `python status.py`.
6. If the post-pull command or the restart fails, automatically roll the
   repo back to the commit it was on before the pull.

## Architecture

```
                 ┌────────────────────┐
GitHub push ───▶ │  Flask /webhook    │
                 │  (app.py)          │──┐
                 └────────────────────┘  │
                                          │
scheduled loop ▶ ┌────────────────────┐  │
                 │  Poller            │──┤
                 │  (poller.py)       │  │
                 └────────────────────┘  │
                                          ▼
                                 ┌──────────────────┐
                                 │  Deployer         │
                                 │  (deploy.py)       │
                                 │  git pull          │
                                 │  post-pull command │
                                 │  restart / rollback│
                                 └────────┬───────────┘
                                          │
                          ┌───────────────┼────────────────┐
                          ▼               ▼                ▼
                 ┌────────────────┐ ┌────────────┐ ┌──────────────────┐
                 │ ProcessManager │ │ target repo │ │ DeploymentHistory │
                 │ (PID file)     │ │ (git dir)   │ │ (SQLite)          │
                 └────────────────┘ └────────────┘ └──────────────────┘
```

Modules:

- `app.py` – Flask app exposing `POST /webhook` and `GET /health`.
- `poller.py` – alternative trigger: compares local `HEAD` to `origin/<branch>`
  on a schedule and deploys when they differ.
- `deploy.py` – the actual deployment routine (`git pull` → post-pull command
  → restart → rollback-on-failure), shared by both triggers.
- `process_manager.py` – starts/stops/checks a single managed process via a
  PID file, so the "restart a service" step is testable with an ordinary
  subprocess instead of a real system service.
- `history.py` – SQLite-backed deployment history (trigger source, commit
  before/after, success, rollback flag, captured output, timestamp).
- `status.py` – CLI to print recent deployment history.
- `config.py` – typed config, loadable from environment variables or a
  `config.json`, or constructed directly (used heavily by the tests).

## Webhook signature verification

GitHub signs each webhook delivery by computing an HMAC-SHA256 over the raw
request body using a secret you configure in the GitHub repo's webhook
settings, and sends it as:

```
X-Hub-Signature-256: sha256=<hex-encoded HMAC>
```

`app.py`'s `verify_signature()` recomputes the same HMAC over
`request.data` (the *raw* bytes, not the parsed JSON — this matters, since
re-serializing JSON can produce different bytes) using the shared secret,
then compares it to the header's value with `hmac.compare_digest`, a
constant-time comparison that avoids leaking timing information an attacker
could use to forge a valid signature byte-by-byte:

```python
expected = hmac.new(secret.encode("utf-8"), payload_body, hashlib.sha256).hexdigest()
provided = signature_header.split("=", 1)[1]
hmac.compare_digest(expected, provided)
```

Requests with a missing or invalid signature get `401`. Valid pushes to a
branch other than the one configured are accepted (`200`) but ignored —
this correctly acknowledges the webhook delivery to GitHub while not
triggering a deployment.

## Configuring a target repo, branch, and restart command

Set these via environment variables (or build a `Config` directly / load a
`config.json` — see `config.py`):

| Variable               | Meaning                                                             | Default                     |
|-------------------------|----------------------------------------------------------------------|------------------------------|
| `WEBHOOK_SECRET`       | Shared secret configured on the GitHub webhook                      | `changeme`                  |
| `TARGET_REPO_DIR`      | Local path to the git repo to deploy                                 | `./target_repo`             |
| `TARGET_BRANCH`        | Branch that triggers a deploy (webhook `ref` / poll comparison)      | `main`                       |
| `POST_PULL_COMMAND`    | Shell command run in the target repo after `git pull` (e.g. `pip install -r requirements.txt`) | `""` (skipped) |
| `RESTART_COMMAND`      | Shell command that (re)starts the target process                    | `""` (skipped)               |
| `PID_FILE`             | Where the process manager tracks the running process's PID          | `./deploy_target.pid`        |
| `HISTORY_DB`           | Path to the SQLite deployment history                                | `./deployment_history.db`    |
| `POLL_INTERVAL_SECONDS`| Seconds between polling checks in polling mode                       | `60`                         |

## Running it

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

export WEBHOOK_SECRET="a-real-secret"
export TARGET_REPO_DIR="/path/to/your/deployed/repo"
export TARGET_BRANCH="main"
export POST_PULL_COMMAND="pip install -r requirements.txt"
export RESTART_COMMAND="python3 /path/to/your/deployed/repo/server.py"
export PID_FILE="/path/to/your/deployed/repo/.deploy.pid"
export HISTORY_DB="/path/to/your/deployed/repo/deployment_history.db"

# 1) Webhook receiver — point a GitHub webhook (content type
#    application/json, secret = $WEBHOOK_SECRET) at http://<host>:5000/webhook
python3 app.py

# 2) Polling mode — no public endpoint needed, run this in a loop instead
python3 -c "
from config import Config
from deploy import Deployer
from process_manager import ProcessManager
from history import DeploymentHistory
from poller import Poller

config = Config.from_env()
deployer = Deployer(config, ProcessManager(config.pid_file), DeploymentHistory(config.history_db))
Poller(config, deployer).run_forever()
"
```

### Viewing deployment history

```
$ python3 status.py
[   3] 2026-09-17T20:44:52.403917+00:00  webhook   11223344 -> 66778899  SUCCESS
[   2] 2026-09-17T20:44:52.403646+00:00  poll      f6a7b8c9 -> 11223344  ROLLED BACK
[   1] 2026-09-17T20:44:52.403221+00:00  webhook   a1b2c3d4 -> f6a7b8c9  SUCCESS
```

`python3 status.py -n 25` shows more history; `-v` also prints the captured
`git pull` / post-pull / restart output for each entry.

## Rollback behavior

If the post-pull command exits non-zero, or the target process fails to stay
running after a restart attempt, the bot runs `git reset --hard <commit_before>`
in the target repo, marks the deployment `rolled_back=True` in history, and
returns failure to the caller. The repo is left exactly where it was before
the failed deployment.

## Tests

```bash
pip install -r requirements.txt
python3 -m unittest discover -s tests -p "test_*.py" -v
```

The suite (30 tests) builds real temporary git repositories (a bare
"remote" plus two clones) and real short-lived subprocesses for every test —
nothing is mocked at the git or process level. It covers: webhook signature
acceptance/rejection, branch filtering, non-push events, end-to-end deploys
against a real repo, rollback on a failing post-pull command, rollback on a
failed restart, deployment history recording (success/failure/rollback),
process-manager start/stop/is_running against real subprocesses with a PID
file (including a stale PID file from a previous process and a corrupt PID
file), config loading/validation, and polling-mode new-commit detection.

CI (`.github/workflows/tests.yml`) runs the same suite on push/PR against
Python 3.11, 3.12, and 3.13.

## Troubleshooting / FAQ

**`python3 status.py` prints "No deployments recorded yet." even though I
know a deploy ran.** `status.py` reads `HISTORY_DB` from the environment
(default `./deployment_history.db`, relative to the current working
directory). If the bot process was started from a different directory, or
with a different `HISTORY_DB` value, it wrote to a different file than the
one `status.py` is now reading. Run it with the same `HISTORY_DB` the bot
uses, e.g. `HISTORY_DB=/path/to/deployment_history.db python3 status.py`.

**The webhook endpoint always returns 401.** The most common cause is that
GitHub is configured with "Content type: application/json" but the
signature is being computed over the wrong bytes. `verify_signature()`
recomputes the HMAC over the *raw* request body (`request.data`), so
anything that re-serializes or reformats the payload before it reaches
Flask (a proxy that pretty-prints JSON, for example) will break the
signature. Confirm `WEBHOOK_SECRET` matches the secret configured on the
GitHub webhook exactly (no trailing whitespace/newline from a `.env` file).

**A deployment "succeeds" but the target process isn't actually running
the new code.** If `RESTART_COMMAND` is empty, `_restart()` treats that as
"nothing to restart" and reports success without touching any process —
this is intentional for setups where the running process picks up changes
some other way (e.g. a reverse proxy or auto-reloading dev server), but if
you expected an actual restart, check that `RESTART_COMMAND` is set.

**Loading `config.json` raises `Unknown key(s) in config.json: ...`.**
This means a key in the file doesn't match a `Config` field (usually a
typo, e.g. `target_branchh`). The error message lists the valid field
names — see the table above for what each one does.

## License

MIT — see [LICENSE](LICENSE).
