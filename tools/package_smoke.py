#!/usr/bin/env python3
"""Check an installed sdb-reader: that the package brought its data along.

The tests run against the checkout, where every file is present. A wheel
carries only what the packaging names, so a data file left out of it shows up
first on a user's machine. This is run with the interpreter of an environment
the built wheel was installed into (``make package-check``), from outside the
checkout, and touches each data file the way a caller does.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from importlib import metadata, resources
from pathlib import Path

import sdb_reader
from sdb_reader import presets

SOURCES = Path(__file__).resolve().parents[1] / "src"


def main() -> int:
    installed = Path(sdb_reader.__file__).resolve()
    if SOURCES in installed.parents:
        print(f"sdb_reader was imported from the checkout's sources: {installed}")
        return 1

    package = resources.files("sdb_reader")
    problems: list[str] = []

    # The marker that the package is typed.
    if not package.joinpath("py.typed").is_file():
        problems.append("py.typed is missing")

    # The schemas of what `read` and `ask` print (SDW-16, SDW-26).
    for name in ("read_record.schema.json", "ask_record.schema.json"):
        try:
            schema = json.loads(package.joinpath(name).read_text("utf-8"))
            if "$schema" not in schema:
                problems.append(f"{name} is no JSON Schema")
        except (OSError, ValueError) as exc:
            problems.append(f"{name}: {exc}")

    # The request fields for known model families (SDW-31).
    try:
        if not presets.shipped_presets():
            problems.append("presets.toml holds no preset")
    except (OSError, ValueError) as exc:
        problems.append(f"presets.toml: {exc}")

    # The regulation's wording of the statements.
    if sdb_reader.canonical_text("H315") is None:
        problems.append("the CLP statements are missing: H315 has no wording")

    # A sentence for every message code in each shipped language (BIB-11).
    for language in ("de", "en"):
        try:
            catalog = sdb_reader.shipped_catalog(language)
            for code, names in sdb_reader.MESSAGE_CODES.items():
                catalog.render(sdb_reader.Message(code, dict.fromkeys(names, 1)))
        except Exception as exc:  # noqa: BLE001 - whatever breaks is the finding
            problems.append(f"catalog {language}: {type(exc).__name__}: {exc}")

    # The command the package installs.
    command = shutil.which("sdb-reader", path=str(Path(sys.executable).parent))
    if command is None:
        problems.append("the command sdb-reader is not installed")
    else:
        done = subprocess.run(  # noqa: S603 -- the command just installed
            [command, "--help"], capture_output=True, text=True, check=False
        )
        if done.returncode != 0:
            problems.append(f"sdb-reader --help ended with {done.returncode}")

    for problem in problems:
        print(f"FAILED: {problem}")
    if problems:
        return 1
    print(
        f"sdb-reader {metadata.version('sdb-reader')} installed at {installed.parent}: complete"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
