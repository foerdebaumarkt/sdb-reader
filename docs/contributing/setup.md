# Setting up and the checks

## The environment

You need [uv](https://docs.astral.sh/uv/) and a supported Python, 3.12 or
newer; uv fetches one if the machine lacks it. The package supports every
Python version still maintained from 3.12 on, and CI runs the tests with
each. Code that the oldest of them does not accept fails `make lint` and
`make type`, which check for it. To run the tests with another version than
your environment's: `uv run --python 3.12 --isolated pytest`.

```bash
make venv            # uv sync --locked: exactly what uv.lock says
```

For the one test that reads a scan with the real program, install
`tesseract` with German language data
([Installing](../usage/installing.md#install-text-recognition)). Without it
the test is skipped on your machine; CI runs it.

## The checks

| Command | Checks |
| --- | --- |
| `make lint` | ruff over the whole tree |
| `make type` | mypy over the whole tree |
| `make deadcode` | vulture: code nothing calls |
| `make test` | the test suite, with the docstring examples and the examples of the documentation |
| `make licenses` | the licence of every installed package against `licenses-allowed.txt` |
| `make docs` | builds the documentation site into `build/site`, with the reference of the exported names made from their descriptions; a description Sphinx cannot render, an exported name the reference lacks, a link that leads nowhere on the site or a page the navigation does not name fails it |
| `make dist` | builds the source distribution and the wheel into `build/release` and checks that the package index can render their description |
| `make package-check` | builds the wheel, installs it by itself and checks that it brought its data files along |
| `make fmt` | not a check: formats the tree with ruff |

Run them all before you open a pull request:

```bash
make lint type deadcode test licenses docs dist package-check
```

The same checks run on every pull request ([CI/CD](ci-cd.md)), together with
the pre-commit hooks and a scan for secrets. Install the hooks locally with
`pre-commit install` if you have pre-commit; they are the same ones CI runs.

## Tests that guard more than code

| Test | Fails when |
| --- | --- |
| `tests/test_specs.py` | a rule in force has no test, or a test names a rule that does not exist or is withdrawn |
| `tests/test_stage_versions.py` | the code of a stage changed and nobody decided about its version ([Stage versions](stage-versions.md)) |
| `tests/test_public_interface.py` | an exported name is missing, undescribed or not listed |
| `tests/test_messages.py` | a shipped catalog lacks a code or names a value the code does not carry |
| `tests/test_read_schema.py` | the output of `read` and its JSON Schema disagree |
| `tests/test_docs_examples.py` | a Python example in the documentation does not run or does not hold what it claims |
| `tests/test_docs.py` | a link in the documentation points nowhere, the two languages of the operator's manual differ in structure, or the list of messages is out of date |
| `tests/test_release.py` | a page is missing from the site's navigation, a link in the README the package index shows needs the repository, or the release workflow could publish from a private repository or a tag that is not the package's version |

## Writing documentation

- The operator's manual exists in German (`docs/bedienung/`) and English
  (`docs/usage/`). Change both together: they have the same pages, the same
  headings and the same code blocks, and a test compares them.
- The lists of all messages are written by a tool. After changing a code or
  a catalog sentence, run `.venv/bin/python tools/docs/message_pages.py`.
- A Python block in `docs/api/` runs in the test suite and should assert
  what the page says. The pages build on one another in the order of
  [the index](../api/README.md).
- A page for developers or contributors is English only.
- The pages are also the documentation site ([Releasing](releasing.md#the-documentation-site)):
  name a new page in the navigation in `docs/index.md`, and look at the
  result with `make docs` (open `build/site/index.html`).
