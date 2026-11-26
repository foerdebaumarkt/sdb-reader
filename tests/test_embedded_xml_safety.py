"""The embedded eSDScom file is read without expanding entities (SDW-11).

Every document here is invented.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from sdb_reader import parse_embedded

LAUGHS = (
    b'<?xml version="1.0"?>\n'
    b"<!DOCTYPE DatasheetFeed [\n"
    b'<!ENTITY a "lol">\n'
    + b"".join(
        b'<!ENTITY %s "%s">\n'
        % (chr(98 + i).encode(), (b"&%s;" % chr(97 + i).encode()) * 10)
        for i in range(9)
    )
    + b"]>\n<DatasheetFeed><Datasheet>&j;</Datasheet></DatasheetFeed>"
)
EXTERNAL = (
    b'<?xml version="1.0"?>\n'
    b'<!DOCTYPE DatasheetFeed [<!ENTITY secret SYSTEM "file:///etc/passwd">]>\n'
    b"<DatasheetFeed><Datasheet>&secret;</Datasheet></DatasheetFeed>"
)
EXTERNAL_SUBSET = (
    b'<?xml version="1.0"?>\n'
    b'<!DOCTYPE DatasheetFeed SYSTEM "http://example.invalid/feed.dtd">\n'
    b"<DatasheetFeed><Datasheet/></DatasheetFeed>"
)
PARAMETER_ENTITY = (
    b'<?xml version="1.0"?>\n'
    b'<!DOCTYPE DatasheetFeed [<!ENTITY % all SYSTEM "file:///etc/passwd"> %all;]>\n'
    b"<DatasheetFeed><Datasheet/></DatasheetFeed>"
)
BARE = b"<!DOCTYPE DatasheetFeed><DatasheetFeed><Datasheet/></DatasheetFeed>"
PLAIN = b"<DatasheetFeed><Datasheet/></DatasheetFeed>"

REFUSED = {
    "billion-laughs": LAUGHS,
    "external-entity": EXTERNAL,
    "billion-laughs-utf16": LAUGHS.decode().encode("utf-16"),
    "external-entity-utf16": EXTERNAL.decode().encode("utf-16"),
    "external-subset": EXTERNAL_SUBSET,
    "parameter-entity": PARAMETER_ENTITY,
    "bare-document-type": BARE,
}


@pytest.mark.spec("SDW-11")
@pytest.mark.parametrize("content", REFUSED.values(), ids=REFUSED.keys())
def test_a_document_type_or_entity_is_refused_at_once(content: bytes) -> None:
    start = time.perf_counter()
    data = parse_embedded("sds.xml", content)
    assert time.perf_counter() - start < 1.0
    assert data.sheet is None
    assert data.unreadable is not None
    assert data.unreadable.code == "embedded-doctype"
    assert data.content is None


@pytest.mark.spec("SDW-11")
def test_a_plain_file_in_utf16_is_still_read() -> None:
    content = (
        '<?xml version="1.0" encoding="UTF-16"?>'
        "<DatasheetFeed><Datasheet><HazardIdentification><HazardLabelling>"
        "<ClpLabellingInfo><ClpHazardStatement><PhraseCode>315</PhraseCode>"
        "</ClpHazardStatement></ClpLabellingInfo></HazardLabelling>"
        "</HazardIdentification></Datasheet></DatasheetFeed>"
    ).encode("utf-16")
    data = parse_embedded("sds.xml", content)
    assert data.sheet is not None
    assert sorted(data.sheet.hazard_codes) == ["H315"]


# Reads each document given as hexadecimal and prints why it was not read.
# The first lines make the import of the compiled parser fail, so that Python
# falls back on the parser written in Python.
_READ_WITH_PYTHONS_OWN_PARSER = """
import sys

sys.modules["_elementtree"] = None

import xml.etree.ElementTree as ET

from sdb_reader import parse_embedded

if not hasattr(ET.XMLParser(), "parser"):
    sys.exit("the compiled parser is still in use")
for document in sys.argv[1:]:
    data = parse_embedded("sds.xml", bytes.fromhex(document))
    print(data.unreadable.code if data.unreadable else "read")
"""


@pytest.mark.spec("SDW-11")
def test_pythons_own_parser_refuses_a_document_type_too() -> None:
    """Where the compiled parser is missing, Python reads XML with one written
    in Python, which reports only some document types to its target."""
    documents = [*REFUSED.values(), PLAIN]
    result = subprocess.run(  # noqa: S603 -- this interpreter, a script above
        [
            sys.executable,
            "-c",
            _READ_WITH_PYTHONS_OWN_PARSER,
            *(document.hex() for document in documents),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.split() == ["embedded-doctype"] * len(REFUSED) + ["read"]
