# CI/CD

Seven workflows live under `.github/workflows/`. Six of them check a change,
and every check below really runs in one of them — a check that is only
documented is not a check. The seventh, `release.yml`, runs for a release
tag and is described in [Releasing](releasing.md).

| Workflow | Runs | Covers |
| --- | --- | --- |
| `pre-commit.yml` | `pre-commit` over **all** files | hygiene hooks, ruff lint + format, mypy, vulture, gitleaks on staged changes, the editor guardrail |
| `tests.yml` | for every supported Python version: `uv sync --locked`, then `pytest`, `make package-check`, `make dist` and `make docs` | the test suite, on exactly the versions in `uv.lock`, with `tesseract` installed so that one test reads a scan with the real program; the built wheel, installed by itself, brings its data files along; the distributions a release would publish pass the package index's check; the documentation site builds without a warning, and its reference holds every exported name with a description (it is not published from here; the run keeps it for a week as the artifact `site`) |
| `gitleaks.yml` | gitleaks over the commits a change adds, weekly over the whole history | secrets |
| `licenses.yml` | `make licenses` | the licence of every package `uv.lock` installs, against `licenses-allowed.txt` |
| `zizmor.yml` | zizmor over the workflows | every action, reusable workflow and container image is pinned to a commit or digest |
| `codeql.yml` | CodeQL over the Python code and the workflows, on every change and weekly | code scanning; findings appear under the repository's Security tab. Only for a public repository: in a private one the job is skipped |

In each workflow a newer push to a pull request cancels the run of the older
one; runs on `main` are left to finish.

`tests.yml` runs its job once per supported Python version (the `suite`
jobs) and then one job named `pytest` that passes only if every one of them
did. A branch rule requires `pytest` alone, so the rule does not change when
a Python version joins or leaves. The versions are listed in three places
that a test holds equal: the matrix in `tests.yml`, the classifiers in
`pyproject.toml`, and, for the oldest, `requires-python`, ruff's
`target-version` and mypy's `python_version`. The licences are checked on
the oldest version, the hooks run on one of the supported ones.

All of them run on GitHub-hosted runners and with every action pinned to a
commit. The checks have a read-only token; `codeql.yml` may also write its
findings, and the jobs of `release.yml` each name the one thing they may do. Keep it that way: a self-hosted runner on a public
repository executes the code of any pull request from a fork, and a mutable
action tag can be moved to other code. Dependabot keeps the pinned commits
current.

`tests.yml` first looks at the files a pull request or push changed and
runs pytest only if one of them is something pytest reads: the package, the
tests, the tools, the specs, the documentation with the READMEs and the
changelog, the workflows, the dependencies or the pytest config. Otherwise it reports green
without running. The decision is a step inside the job, not a `paths:` filter
on the trigger, because a required check whose workflow never starts leaves
the pull request pending for good. Keep the step's file list in line with what
the suite reads; a project that adds another directory the tests read adds it
there.

Because `pre-commit.yml` runs with `--all-files`, the hooks judge the whole
repository, not just what a pull request touched. A check added here therefore
speaks about code that was already in the tree.

**Editor guardrail**: `.gitignore` keeps `.vscode/` and `.idea/` out, and the
`no-editor-files` hook fails the build if one is committed anyway — see
[editor-agnostic.md](editor-agnostic.md).

**Dead code**: `vulture` reports what nothing calls. `tests/` is deliberately
not among the scanned paths in `[tool.vulture]`, so a function whose only
caller is its own test counts as uncalled. See `make deadcode`.

## Pre-commit Setup

The repository includes a comprehensive pre-commit configuration with:

### Hygiene Hooks

- Trailing whitespace removal
- End-of-file fixing
- Merge conflict detection
- YAML/JSON/TOML validation
- Large file detection

### Security

- Branch protection (prevents direct commits to main)
- Secrets scanning with gitleaks

### Policy

- No committed editor files (`.vscode/`, `.idea/`)

### Python Quality

- Ruff linting and formatting
- MyPy type checking
- Vulture dead-code gate

### Local Development

To use pre-commit hooks locally:

```bash
# Install pre-commit (if not already installed)
uv tool install pre-commit

# Install the hooks
pre-commit install

# Run hooks on all files (optional)
pre-commit run --all-files
```

After installation, hooks will run automatically on each commit. You can bypass hooks temporarily with `git commit --no-verify` if needed.
