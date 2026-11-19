"""Where a link in a documentation page leads on the documentation site.

The pages under ``docs/`` are written to be read on GitHub: a link to a spec,
to the changelog or to a file of the repository is a relative path. The site
holds only what is under ``docs/``, so there such a link would lead nowhere.
``docs/conf.py`` runs every page through :func:`for_site` before Sphinx
reads it: a link that leaves ``docs/`` then points at the file on GitHub, at
the tag the site is built for, and the link to the changelog points at the
site's own page of it.
"""

from __future__ import annotations

import posixpath
import re

# A Markdown link or image, inline: [text](target) with nothing but the
# target in the brackets. A link with a title in quotes is not used here.
_LINK = re.compile(r"(?P<head>!?\[[^\]]*\]\()(?P<target>[^)\s]+)(?P<tail>\))")
_FENCE = re.compile(r"^(\s*)(```|~~~)")
_SCHEME = re.compile(r"[a-z][a-z0-9+.-]*:")

# Pages of the repository the site carries itself, by their path in the
# repository: the link goes to the site's page (a document name of Sphinx,
# from the root of docs/), not to GitHub.
ON_THE_SITE = {"CHANGELOG.md": "changelog"}


def for_site(text: str, *, docname: str, repository: str, ref: str) -> str:
    """*text* of the page *docname* with its links fit for the site.

    *docname* is the page's path below ``docs/`` without ``.md``, as Sphinx
    names it. A link that stays inside ``docs/`` is left alone, and so is
    one to another site and everything inside a fenced block.

    >>> for_site("[rules](../specs/README.md#ids)", docname="how-it-works",
    ...          repository="https://github.com/o/r", ref="v1.2.3")
    '[rules](https://github.com/o/r/blob/v1.2.3/specs/README.md#ids)'
    >>> for_site("[news](../../CHANGELOG.md)", docname="usage/installing",
    ...          repository="https://github.com/o/r", ref="main")
    '[news](../changelog.md)'
    >>> for_site("[next](reading.md)", docname="usage/installing",
    ...          repository="https://github.com/o/r", ref="main")
    '[next](reading.md)'
    """
    folder = posixpath.dirname(docname)

    def replace(found: re.Match[str]) -> str:
        target = found["target"]
        if _SCHEME.match(target):
            return found[0]
        path, mark, anchor = target.partition("#")
        if not path:
            return found[0]
        # From the repository's root: docs/<folder>/<path>, normalised.
        in_repository = posixpath.normpath(posixpath.join("docs", folder, path))
        if in_repository == "docs" or in_repository.startswith("docs/"):
            return found[0]
        if in_repository in ON_THE_SITE:
            page = posixpath.relpath(ON_THE_SITE[in_repository], folder or ".")
            new = f"{page}.md"
        else:
            new = f"{repository}/blob/{ref}/{in_repository}"
        return f"{found['head']}{new}{mark}{anchor}{found['tail']}"

    lines = []
    fence: str | None = None
    for line in text.split("\n"):
        opened = _FENCE.match(line)
        if fence is None and opened:
            fence = opened[2]
        elif fence is not None and line.strip().startswith(fence):
            fence = None
        elif fence is None:
            line = _LINK.sub(replace, line)
        lines.append(line)
    return "\n".join(lines)
