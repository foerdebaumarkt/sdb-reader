#!/usr/bin/env python3
"""Put the documentation of every released version together as one site.

Each release carries its documentation as a file,
``sdb-reader-<version>-docs.tar.gz`` (docs/contributing/releasing.md). The
release workflow fetches these files and calls this to build what GitHub
Pages serves: one folder per version, ``latest/`` as a copy of the newest,
a start page that leads there and ``versions.html`` with the list.

    .venv/bin/python tools/docs/assemble_site.py <folder with the files> <output folder>

Nothing is built again here: an edition is exactly what its release built.
"""

from __future__ import annotations

import html
import re
import shutil
import sys
import tarfile
from pathlib import Path

_ARCHIVE = re.compile(r"sdb-reader-(\d+)\.(\d+)\.(\d+)-docs\.tar\.gz")

_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
{head}<title>{title}</title>
<style>
body {{ font-family: system-ui, sans-serif; max-width: 40rem; margin: 3rem auto; padding: 0 1rem; line-height: 1.5; }}
li {{ margin: 0.3rem 0; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _versions(folder: Path) -> dict[tuple[int, int, int], Path]:
    found = {}
    for path in sorted(folder.iterdir()):
        match = _ARCHIVE.fullmatch(path.name)
        if match:
            found[(int(match[1]), int(match[2]), int(match[3]))] = path
    return found


def assemble(archives: Path, out: Path) -> list[str]:
    """Build the site under *out* from the files in *archives*; the versions, newest first.

    *out* must not exist yet. A file that is no documentation archive of a
    release is left aside; an archive that does not hold the one folder
    ``site/`` is an error.
    """
    versions = _versions(archives)
    if not versions:
        raise ValueError(f"no sdb-reader-<version>-docs.tar.gz in {archives}")
    out.mkdir(parents=True)
    names = []
    for version in sorted(versions, reverse=True):
        name = ".".join(str(part) for part in version)
        unpacked = out / f".unpack-{name}"
        with tarfile.open(versions[version]) as archive:
            # "data": no absolute path, no link out of the folder, no device.
            archive.extractall(unpacked, filter="data")
        if sorted(path.name for path in unpacked.iterdir()) != ["site"]:
            raise ValueError(f"{versions[version].name} does not hold the folder site/")
        (unpacked / "site").rename(out / name)
        unpacked.rmdir()
        names.append(name)
    shutil.copytree(out / names[0], out / "latest")
    (out / "index.html").write_text(
        _PAGE.format(
            head='<meta http-equiv="refresh" content="0; url=latest/">\n'
            '<link rel="canonical" href="latest/">\n',
            title="sdb-reader documentation",
            body='<p>The documentation of the newest version is at <a href="latest/">latest/</a>.</p>',
        ),
        encoding="utf-8",
    )
    items = "\n".join(
        f'<li><a href="{html.escape(name)}/">{html.escape(name)}</a>'
        + (
            ' (the newest, also at <a href="latest/">latest/</a>)'
            if name == names[0]
            else ""
        )
        + "</li>"
        for name in names
    )
    (out / "versions.html").write_text(
        _PAGE.format(
            head="",
            title="sdb-reader documentation: all versions",
            body=f"<h1>sdb-reader documentation</h1>\n<p>One edition per released version.</p>\n<ul>\n{items}\n</ul>",
        ),
        encoding="utf-8",
    )
    # GitHub Pages would otherwise run the files through Jekyll, which drops
    # folders that begin with an underscore: the site's _static/.
    (out / ".nojekyll").write_text("", encoding="utf-8")
    return names


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    names = assemble(Path(argv[0]), Path(argv[1]))
    print("editions: " + ", ".join(names))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
