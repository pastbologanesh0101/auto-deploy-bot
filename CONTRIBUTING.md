# Contributing

Thanks for considering a contribution to Auto Deployment Bot.

## Running the tests

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

git config --global user.email "you@example.com"   # only needed once, if unset
git config --global user.name "Your Name"

python3 -m unittest discover -s tests -p "test_*.py" -v
```

The suite builds real temporary git repositories and short-lived subprocesses
for every test (nothing is mocked at the git or process level), so `git`
must be on `PATH` and a git identity must be configured.

## Code style

- Plain-function/dataclass style, matching the existing modules — avoid
  introducing new frameworks or abstraction layers for small features.
- Docstrings on every public class and function explaining *why*, not just
  *what* (see `process_manager.py` or `app.py`'s `verify_signature` for the
  expected level of detail).
- Format error/log strings with `.format()` to match the rest of the
  codebase rather than mixing in f-strings.
- No new third-party dependencies unless there's no reasonable way around it.

## Submitting changes

1. Fork the repo and create a branch for your change.
2. Add or update tests under `tests/` for any behavior change — the suite
   uses real git repos/subprocesses rather than mocks, so new tests should
   follow that pattern (see `tests/helpers.py`).
3. Run the full test suite locally and make sure it passes on the Python
   versions listed in `.github/workflows/tests.yml`.
4. Open a pull request describing the change and why it's needed.
