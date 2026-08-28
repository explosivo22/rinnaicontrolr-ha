# Contributing

## Prerequisites

- Python **3.12** (pinned in `.python-version`; CI also tests 3.13 for
  forward compatibility, but 3.12 is the primary dev target)
- [`uv`](https://docs.astral.sh/uv/) — used to create the venv and install
  dependencies - e.g.,
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```

## Setup

```bash
# Create .venv - uses the Python version pinned in .python-version
uv venv

# Install pinned dev/CI packages
uv pip install --python .venv -r requirements_dev.txt

# Install component runtime dependencies - read from manifest.json
REQS=$(.venv/bin/python -c "import json; f=open('custom_components/rinnai/manifest.json'); reqs=json.load(f).get('requirements', []); print(' '.join(reqs))")
uv pip install --python .venv $REQS
```

## Pre-commit hooks

Install the git pre-commit hook:

```bash
.venv/bin/pre-commit install
```

This requires that `ruff check`, `ruff format --check`, `mypy`, and
`pytest` run and pass ugainst staged/changed files before the
commit completes (config in `.pre-commit-config.yaml`). These can also all be run
manually against the whole tree without committing:

```bash
.venv/bin/pre-commit run --all-files
```

## Running checks manually

These are the same commands CI runs (`.github/workflows/test-with-homeassistant.yaml`):

```bash
# Unit tests
PYTHONPATH="$(pwd)" .venv/bin/pytest tests/ -v --tb=short

# Lint
.venv/bin/ruff check custom_components/rinnai/

# Format check
.venv/bin/ruff format custom_components/rinnai/ --check

# Type check (informational in CI — doesn't fail the build there, but should
# be kept clean)
.venv/bin/mypy custom_components/rinnai/ --ignore-missing-imports --no-error-summary
```

## Updating pinned versions

`requirements_dev.txt` is pinned deliberately, and CI installs from that same
file (`uv pip install --system -r requirements_dev.txt`) so local and CI
results always match. To bump a tool version:

1. Update the version in `requirements_dev.txt`.
2. Run `uv pip install --python .venv -r requirements_dev.txt` and re-run the
   full check suite locally to confirm nothing regresses under the new
   version(s).
3. Commit the `requirements_dev.txt` change on its own, so a version bump is
   never accidentally bundled into an unrelated feature/fix PR.

The component's own runtime dependencies (`aiorinnai`, `PyJWT`) are pinned
separately in `custom_components/rinnai/manifest.json`, not here — `PyJWT` is
intentionally left loose (`>=2.0.0`) since it has to coexist with whatever
version other installed HA integrations require in the same shared
environment.
