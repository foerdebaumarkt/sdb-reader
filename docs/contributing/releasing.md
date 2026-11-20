# Releasing

For maintainers: how a version is released, what the workflow does with it,
and what has to be set up once outside the repository. The rules behind it
are BIB-13, BIB-18, BIB-22 and BIB-23 in
[specs/bibliothek.md](../../specs/bibliothek.md).

A release is a tag `v<version>` on `main`. Everything else follows from the
tag: `.github/workflows/release.yml` builds the package and the
documentation, publishes the package on the Python Package Index, creates
the GitHub release and deploys the documentation site. Nobody builds or
uploads a package by hand.

## Cutting a release

1. **Choose the version** by what changed since the last release
   ([What is promised](../api/stability.md)): a rise of `EXTRACTION_VERSION`
   or `PARSER_VERSION` is at least a minor version. Before 1.0 a minor
   version may break.
2. **Open a pull request** that sets `version` in `pyproject.toml`, refreshes
   `uv.lock` (`uv lock`) and turns the changelog's "Unreleased" section into
   the release's: a new heading `## <version> – <date>` under an empty
   "Unreleased". Name every breaking change under "Breaking" and every rise
   of a stage version, with what a caller has to do about texts and readings
   it kept. Where a page names a version as an example, move it along.
3. **Merge it**, and wait for the checks on `main`.
4. **Tag the merge commit** and push the tag:

   ```bash
   git tag -a v0.10.0 -m "sdb-reader 0.10.0" <commit on main>
   git push origin v0.10.0
   ```

5. **Watch the run** of `release` under Actions. The jobs that publish wait
   for an approval if their environments ask for one (see below).

A tag cannot be released twice, and a version once on the index cannot be
replaced. If a release is wrong, fix it and release the next patch version.

## What the workflow does

| Job | Does | Runs |
| --- | --- | --- |
| `build` | checks the tag, runs the tests, builds the source distribution and the wheel (`make dist`), installs the wheel by itself (`make package-check`), builds the documentation site (`make docs`) | always |
| `pypi` | publishes the distributions on the Python Package Index | only for a public repository |
| `release` | creates the GitHub release: the changelog's section as its text; the distributions and the built documentation as its files | when `build` passed and `pypi` passed or was skipped |
| `pages` | puts the documentation of every release together and deploys it to GitHub Pages | only for a public repository |

**The tag is checked before anything is built** (`tools/release.py check`).
It is released only if

- it has the form `v<major>.<minor>.<patch>`,
- it is the `version` in `pyproject.toml`,
- it is not older than the first public version, 0.9.0,
- the changelog's newest release section is this version, with its date,
- its commit is on `main`.

A tag that fails one of these releases nothing; delete it and set it right.

**Nothing leaves a private repository.** `build` asks GitHub whether the
repository is public, and `pypi` and `pages` run only if it is. In a private
repository a tag gives a GitHub release with the built files and nothing
else. The package index is a second lock: it takes a package only from this
workflow in this repository (see below).

**The package is published without a stored secret.** The index trusts the
workflow itself ("trusted publishing"): GitHub signs a short-lived token
that says which repository, workflow and environment is asking, and the
index checks it against what its project settings name. There is no API
token to leak or to rotate.

## The documentation site

The site is at <https://foerdebaumarkt.github.io/sdb-reader/> and holds one
edition per released version:

| Address | Shows |
| --- | --- |
| `/` | leads to `latest/` |
| `/latest/` | the edition of the newest version |
| `/<version>/` | the edition of that version |
| `/versions.html` | the list of all editions |

An edition is what `make docs` builds: the pages under `docs/` through
Sphinx (`docs/conf.py`, navigation in `docs/index.md`), the changelog, and
the [reference](../reference.md) of the exported names, which Sphinx makes
from the descriptions in the code. Generated pages are not committed.

**Each release carries its edition as a file**,
`sdb-reader-<version>-docs.tar.gz`, and the site is put together from these
files (`tools/docs/assemble_site.py`), not built again from the tags. So an
edition is exactly what its release built and never changes, and a release
never fails because the documentation of an old tag no longer builds. To
take an edition off the site, delete that file from its release and run the
`pages` job of the newest release again.

The pages are written to be read on GitHub too. What the site needs beyond
that:

- **Links that leave `docs/`** (to a spec, to a tool's README, to the
  licence) are relative paths in the files, which work on GitHub. For the
  site, `docs/conf.py` turns them into links to the file on GitHub at the
  tag the edition is built for (`tools/docs/site_links.py`); the link to
  `CHANGELOG.md` leads to the site's own page of it.
- **A new page** is added to the navigation in `docs/index.md`. A page the
  navigation does not name fails `make docs` and a test.
- **A new exported name** is added to `docs/reference.md`, in the group it
  belongs to. A name the page lacks fails `make docs` and a test.
- **`README.md` at the root** is what the package index shows. Its links are
  absolute, to the site's newest edition or to the repository, because a
  relative link leads nowhere there; a test holds that each leads to a file
  that exists.
- **The diagram** in [How it works](../how-it-works.md) is drawn by GitHub
  and shown as its text on the site: drawing it there would need a script
  fetched from another server on every visit.

Every pull request builds the site as part of the tests and keeps it for a
week as the artifact `site` of the run, to look at a change to the pages
before it is merged.

## Set up once

These are settings outside the repository's files. Until they are made, a
release stops at the job that needs them.

**On the Python Package Index** (<https://pypi.org/manage/account/publishing/>),
a pending publisher for the project `sdb-reader`:

| Field | Value |
| --- | --- |
| PyPI project name | `sdb-reader` |
| Owner | `foerdebaumarkt` |
| Repository name | `sdb-reader` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

**In the repository's settings:**

- **Pages:** under "Build and deployment", the source is "GitHub Actions".
- **Environments:** `pypi` and `github-pages`. For each, name the people who
  have to approve a deployment, and restrict it to tags `v*`.
- **Tags:** a rule that only maintainers create tags `v*`.
- **Code security:** private vulnerability reporting, secret scanning with
  push protection and Dependabot alerts switched on. Code scanning runs from
  `codeql.yml` and needs no switch.
- **Branch rule for `main`:** the required checks as before (`pytest`,
  `pre-commit`, `licenses`, `gitleaks`, `zizmor`).
