# CI/CD

Seven workflows live under `.github/workflows/`. Six of them check a change,
and every check below really runs in one of them — a check that is only
documented is not a check. The seventh, `release.yml`, runs for a release
tag and is described in [Releasing](releasing.md).

| Workflow | Runs | Covers |
| --- | --- | --- |
| `pre-commit.yml` | `pre-commit` over **all** files | hygiene hooks, ruff lint + format, mypy, vulture, regexploit, gitleaks on staged changes, the editor guardrail |
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

**Security rules**: ruff runs flake8-bandit's rules (`S`): a subprocess, an
opened URL, `eval`, XML parsed without protection. The package reads files from
anyone, so each finding is fixed or carries a `noqa` that says why it is safe.
Several other rule sets are on although nothing in the tree breaks them today
(`A`, `PIE`, `PTH`, `G`, `LOG`, `PGH`, `N`, `TID`), so that it stays that way;
`ruff.toml` names them.

**Slow regular expressions**: the `regexploit` hook looks at every pattern
written as a literal under `src/` and `tools/` and fails on one that takes
cubic or worse time on a long run of one character ("x" followed by thousands
of spaces). It does not see a pattern put together at runtime, and it misses
the exponential cases; those are CodeQL's, which reports them on every pull
request. regexploit exits 0 even when it finds something, so the hook reads
its report. A test in `tests/test_regex_runtime.py` holds the patterns that
were rewritten for this to a time limit.

**Reading time**: `tests/test_reading_time.py` is a property test with
Hypothesis. It puts a long run of one mark, letter, word or piece of a label
(some 15,000 to 30,000 characters) into an invented sheet at a place the
parser reads, sends the text through the same normalisation as an extracted
PDF's, and fails when one reading takes two seconds or more. It measures the
time instead of judging a pattern by its shape, so it also finds what
regexploit cannot: a pattern put together at runtime, two patterns that read
the same run one after the other, or code that goes over a run again for each
line. In CI it runs a fixed set of 40 examples (the profile `ci` in
`tests/conftest.py`), a few seconds, the same on every run; before a release,
`HYPOTHESIS_PROFILE=thorough` tries 2,000 random ones (about a minute and a
half).

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

- Ruff linting and formatting, security rules (`S`) included
- regexploit: regular expressions with polynomial worst case
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
