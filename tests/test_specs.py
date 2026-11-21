"""The specs and the tests agree (specs/README.md).

Every active rule in specs/*.md is pinned by at least one test carrying
``@pytest.mark.spec("<ID>")``; no test names a rule that does not exist, was
withdrawn, or is only proposed; no spec defines an ID twice.
"""

from __future__ import annotations

import ast
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# - **SDB-4.** Die Regel.
# - **SDW-12.** *Zurückgezogen 2026-11-16:* ...
# - **SDW-99.** *Vorgeschlagen:* ...
# The specs are German (specs/README.md), so are the markers.
_RULE = re.compile(r"^- \*\*([A-Z]+-\d+)\.\*\*(.*)$", re.MULTILINE)
_WITHDRAWN = re.compile(r"^\s*\*Zurückgezogen \d{4}-\d{2}-\d{2}")
_PROPOSED = re.compile(r"^\s*\*Vorgeschlagen:\*")

ACTIVE = "active"
WITHDRAWN = "withdrawn"
# Decided but not built yet: the ID is taken, and no test can pin it.
PROPOSED = "proposed"


def _state(text: str) -> str:
    if _WITHDRAWN.match(text):
        return WITHDRAWN
    if _PROPOSED.match(text):
        return PROPOSED
    return ACTIVE


def _rules(specs: Path) -> tuple[dict[str, str], list[str]]:
    """Each rule ID -> its state, and the IDs defined more than once."""
    found: list[tuple[str, str]] = []
    for path in sorted(specs.glob("*.md")):
        if path.name == "README.md":
            continue
        for match in _RULE.finditer(path.read_text(encoding="utf-8")):
            found.append((match.group(1), _state(match.group(2))))
    counts = Counter(rule_id for rule_id, _ in found)
    return dict(found), sorted(rule_id for rule_id, n in counts.items() if n > 1)


def _is_spec_marker(node: ast.AST) -> bool:
    """``pytest.mark.spec`` -- the callee of a spec marker."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == "spec"
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
        and isinstance(node.value.value, ast.Name)
        and node.value.value.id == "pytest"
    )


def _references(tests: Path) -> dict[str, list[str]]:
    """Each rule ID a ``spec`` marker names -> the files naming it."""
    found: dict[str, list[str]] = {}
    for path in sorted(tests.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and _is_spec_marker(node.func):
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        found.setdefault(arg.value, []).append(path.name)
    return found


def _violations(specs: Path, tests: Path) -> list[str]:
    rules, duplicates = _rules(specs)
    references = _references(tests)
    problems = [f"{rule_id} is defined more than once" for rule_id in duplicates]
    problems += [
        f"{rule_id} has no test"
        for rule_id, state in sorted(rules.items())
        if state == ACTIVE and rule_id not in references
    ]
    for rule_id, files in sorted(references.items()):
        where = ", ".join(sorted(set(files)))
        if rule_id not in rules:
            problems.append(f"{rule_id} is no rule ({where})")
        elif rules[rule_id] != ACTIVE:
            problems.append(f"{rule_id} is {rules[rule_id]} ({where})")
    return problems


def test_the_specs_and_the_tests_agree() -> None:
    assert _violations(ROOT / "specs", ROOT / "tests") == []


def test_the_check_reads_the_rules() -> None:
    """Guards the parser: no rules found would make every check pass."""
    rules, _ = _rules(ROOT / "specs")

    assert {f"SDW-{n}" for n in range(1, 14)} <= set(rules)
    assert {f"SDB-{n}" for n in (1, 4, 20, 49, 66, 75, 110)} <= set(rules)
    assert rules["SDB-4"] == ACTIVE
    assert rules["SDB-83"] == WITHDRAWN
    assert rules["SDW-12"] == WITHDRAWN
    assert rules["SDB-22"] == WITHDRAWN


def test_the_check_sees_a_violation(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    specs.mkdir()
    (specs / "README.md").write_text("- **DEL-99.** Only an example.\n")
    (specs / "area.md").write_text(
        "- **DEL-1.** Pinned.\n"
        "- **DEL-2.** *Zurückgezogen 2026-11-02:* War eine Regel.\n"
        "- **DEL-3.** Defined twice.\n"
        "- **DEL-3.** Defined twice.\n"
        "- **DEL-4.** Never tested.\n"
        "- **DEL-5.** *Vorgeschlagen:* Not built yet.\n"
        "- **DEL-6.** *Vorgeschlagen:* Not built, and nobody claims it is.\n"
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "test_x.py").write_text(
        "import pytest\n\n"
        '@pytest.mark.spec("DEL-1", "DEL-3")\n'
        "def test_a(): ...\n\n"
        '@pytest.mark.spec("DEL-2")\n'
        "def test_b(): ...\n\n"
        '@pytest.mark.spec("DEL-9")\n'
        "class TestC: ...\n\n"
        '@pytest.mark.spec("DEL-5")\n'
        "def test_d(): ...\n"
    )

    assert _violations(specs, tests) == [
        "DEL-3 is defined more than once",
        "DEL-4 has no test",
        "DEL-2 is withdrawn (test_x.py)",
        "DEL-5 is proposed (test_x.py)",
        "DEL-9 is no rule (test_x.py)",
    ]
