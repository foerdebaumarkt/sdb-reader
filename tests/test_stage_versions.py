"""Whoever changes a stage's code decides about its version (BIB-5)."""

from __future__ import annotations

import ast
import hashlib
import io
import tokenize
from pathlib import Path

import pymupdf
import pytest

import sdb_reader

PACKAGE = Path(sdb_reader.__file__).parent

# What each stage is made of, and its code's fingerprint at the version named.
STAGES: dict[str, tuple[tuple[str, ...], int, str]] = {
    "EXTRACTION_VERSION": (
        ("extraction.py", "layout.py", "line_breaks.py"),
        2,
        "edd646c6bcd02e5a",
    ),
    "PARSER_VERSION": (
        (
            "clp_statements_de.json",
            "compliance.py",
            "messages.py",
            "parser.py",
            "pictograms.py",
            "reading.py",
            "schema.py",
            "serialise.py",
            "statements.py",
            "verification.py",
        ),
        20,
        "9fa005867ee1d128",
    ),
}


def _docstring_lines(source: bytes) -> set[int]:
    """The lines a docstring stands on."""
    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        if not isinstance(
            node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        first = node.body[0] if node.body else None
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        ):
            lines.update(range(first.lineno, (first.end_lineno or first.lineno) + 1))
    return lines


# Nothing of the code: comments, line breaks inside a statement, the frame.
_LAYOUT = {tokenize.COMMENT, tokenize.NL, tokenize.ENCODING, tokenize.ENDMARKER}
# The end of a statement and the depth of a block are code; how they are
# spelled (a line ending, so many blanks) is not.
_STRUCTURE = {
    tokenize.NEWLINE: "<newline>",
    tokenize.INDENT: "<indent>",
    tokenize.DEDENT: "<dedent>",
}


def _code(source: bytes) -> bytes:
    """The tokens of *source* without comments, docstrings and layout.

    Tokens and not the syntax tree: ``ast.dump`` writes the same code
    differently from one Python version to the next, and the fingerprint has
    to be the same on every version the tests run with (BIB-16).
    """
    docstrings = _docstring_lines(source)
    return "\0".join(
        _STRUCTURE.get(token.type, token.string)
        for token in tokenize.tokenize(io.BytesIO(source).readline)
        if token.type not in _LAYOUT and token.start[0] not in docstrings
    ).encode()


def fingerprint(files: tuple[str, ...]) -> str:
    """Of the code as Python reads it: comments, docstrings and layout leave it alone."""
    digest = hashlib.sha256()
    for name in files:
        source = (PACKAGE / name).read_bytes()
        if name.endswith(".py"):
            source = _code(source)
        digest.update(name.encode() + b"\0" + source + b"\0")
    return digest.hexdigest()[:16]


@pytest.mark.spec("BIB-5")
@pytest.mark.parametrize("constant", sorted(STAGES))
def test_a_changed_stage_asks_for_a_decision_about_its_version(constant: str) -> None:
    files, version, known = STAGES[constant]

    found = fingerprint(files)

    assert found == known, (
        f"The code behind {constant} changed. If the same input can now give "
        f"another result, raise {constant} in versions.py and here; then set "
        f'this stage\'s fingerprint to "{found}".'
    )
    assert getattr(sdb_reader, constant) == version


@pytest.mark.spec("BIB-5")
def test_comments_docstrings_and_layout_leave_the_fingerprint_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setitem(globals(), "PACKAGE", tmp_path)
    (tmp_path / "a.py").write_text('def f():\n    """One."""\n    return 1\n')
    before = fingerprint(("a.py",))

    (tmp_path / "a.py").write_text(
        'def f():\n    """Another."""\n\n    # why\n    return   1\n'
    )
    same = fingerprint(("a.py",))
    (tmp_path / "a.py").write_text('def f():\n    """One."""\n    return 2\n')

    assert same == before
    assert fingerprint(("a.py",)) != before


@pytest.mark.spec("BIB-5")
def test_a_statement_moved_out_of_its_block_changes_the_fingerprint(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Indentation is code: the same words at another depth do something else."""
    monkeypatch.setitem(globals(), "PACKAGE", tmp_path)
    (tmp_path / "a.py").write_text(
        "def f(x):\n    if x:\n        x = 1\n        return x\n"
    )
    inside = fingerprint(("a.py",))

    (tmp_path / "a.py").write_text(
        "def f(x):\n    if x:\n        x = 1\n    return x\n"
    )

    assert fingerprint(("a.py",)) != inside


@pytest.mark.spec("BIB-4")
def test_the_extraction_stage_names_its_version_and_the_pdf_librarys() -> None:
    assert sdb_reader.extraction_stage() == (
        f"{sdb_reader.EXTRACTION_VERSION}+pymupdf-{pymupdf.__version__}"
    )
    assert isinstance(sdb_reader.PARSER_VERSION, int)
