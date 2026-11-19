# Contributing

Issues and pull requests are welcome, in German or English.

This is the short entry. The detail is in
[docs/contributing/](docs/contributing/README.md): setting up, how a change
runs and how to read the German specs, stage versions, how a change is
measured, adding a language.

## Before you start

For anything larger than a fix, open an issue first and say what you want to
change. That saves you work if the change does not fit.

A contribution stands under the project's licence (AGPL-3.0-or-later). Before
a larger contribution is taken, an agreement about its rights may become
necessary; the issue is the place to settle that.

## Local workflow

Needs [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.

```bash
make venv            # uv sync --locked: exactly what uv.lock says
make lint type deadcode test licenses docs dist package-check
```

The same checks run on every pull request (see `docs/contributing/ci-cd.md`), and a pull
request is merged only when they pass. Workflows on a first pull request from
a new contributor start after a maintainer has approved the run.

## What a pull request should hold

- One change, with a test that fails without it.
- A change of behaviour comes with its rule: first the spec, then the code,
  and the test names the rule (`specs/README.md`). The specs are in German;
  `docs/contributing/changes-and-specs.md` helps if you do not read it.
- No editor-specific files (`docs/contributing/editor-agnostic.md`).
- No secrets, in code, tests or logs. gitleaks scans every commit.
- No supplier's sheet, name, address or number, in a test, a spec, a commit
  or an issue. Use invented ones (`docs/contributing/measuring.md`).
- A change to dependencies comes with the updated `uv.lock` (`uv lock`).
- A new dependency whose licence is not in `licenses-allowed.txt` fails the
  `licenses` check. Say in the pull request why the licence is acceptable
  before adding it to the list.

## The public interface

What the package `sdb_reader` exports is promised to its users
(`specs/bibliothek.md`). A change to one of those names, its parameters or
what it returns needs an issue first.

A change to the code that turns a PDF into text, or a text into a reading,
fails `tests/test_stage_versions.py` until you have decided whether the
stage's version rises; the failure says what to do.

## Docstrings

The reference of the documentation site is made from them (`make docs`).
They are written so that Sphinx and other tools render them the same:

- prose in paragraphs, lists with `-`, examples as a Python session (`>>>`);
- code in double backticks, also the names of other functions;
- no single backticks, Markdown links, headings, tables, fenced blocks or
  cross-reference syntax (`:func:`); name a function in double backticks.

An example in a docstring is run by the test suite: it has to show the result
the code really gives.

## Licence

Contributions are accepted under the GNU Affero General Public License,
version 3 or later, the licence of this repository (`LICENSE`).

## Security problems

Not in an issue: see `SECURITY.md`.
