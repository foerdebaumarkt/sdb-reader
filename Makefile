.PHONY: venv fmt lint type test unit deadcode licenses docs dist package-check

VENV=.venv
PY=$(VENV)/bin/python

# Exactly what uv.lock says, like CI. --locked fails on a lock that no longer
# matches pyproject.toml; run `uv lock` after changing dependencies.
venv:
	uv sync --locked

fmt:
	$(PY) -m ruff format

lint:
	$(PY) -m ruff check .

type:
	$(PY) -m mypy .

# Code nothing calls. Paths and threshold live in pyproject under
# [tool.vulture]; tests/ is deliberately not among them. To look below the
# threshold while hunting, say so: `$(PY) -m vulture --min-confidence 0`.
deadcode:
	$(PY) -m vulture

# Every installed package's licence against licenses-allowed.txt. Read from
# the packages' own metadata in .venv, so it needs no network and judges
# exactly what uv.lock installs.
licenses:
	$(PY) -m piplicenses --allow-only="$$(grep -v -e '^\#' -e '^$$' licenses-allowed.txt | paste -sd ';' -)"

unit:
	$(PY) -m pytest -q

test: unit

# The documentation site (docs/contributing/releasing.md): the pages under
# docs/ through Sphinx, into build/site; not in git. The reference of what
# the package exports (BIB-1) is one of its pages, made from the
# descriptions in the code. A warning fails the build: a description Sphinx
# cannot render, a link that leads nowhere on the site, a page the
# navigation does not name. Then the built reference is asked for every
# exported name and its description (tools/docs/reference_names.py).
docs:
	rm -rf build/site
	$(PY) -m sphinx --builder html --fail-on-warning --keep-going --quiet \
		docs build/site
	$(PY) tools/docs/reference_names.py build/site/reference.html

# What a release puts on the package index: the source distribution and the
# wheel, into build/release, checked the way the index checks them (its
# description must render; a warning counts). The release workflow builds
# exactly this (docs/contributing/releasing.md).
dist:
	rm -rf build/release
	uv build --sdist --wheel --out-dir build/release
	$(PY) -m twine check --strict build/release/*

# Build the wheel, install it into an environment of its own and check that
# it brought its data files along (tools/package_smoke.py). Run from build/,
# so that nothing is imported from the checkout.
package-check:
	# What setuptools left from earlier builds goes first: it copies the
	# package to build/lib and never clears it, and it reads the file list of
	# an existing egg-info. Either would put a file into the wheel that the
	# packaging no longer names.
	rm -rf build/dist build/smoke build/lib build/bdist.* src/*.egg-info
	uv build --wheel --out-dir build/dist
	uv venv --python $(PY) build/smoke
	uv pip install --python build/smoke/bin/python build/dist/*.whl
	cd build && smoke/bin/python ../tools/package_smoke.py
