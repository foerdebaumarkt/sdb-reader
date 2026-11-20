"""The embedded eSDScom file is read without expanding entities (SDW-11).

Every document here is invented.
"""

from __future__ import annotations

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


@pytest.mark.spec("SDW-11")
@pytest.mark.parametrize(
    "content",
    [
        LAUGHS,
        EXTERNAL,
        LAUGHS.decode().encode("utf-16"),
        EXTERNAL.decode().encode("utf-16"),
    ],
    ids=[
        "billion-laughs",
        "external-entity",
        "billion-laughs-utf16",
        "external-entity-utf16",
    ],
)
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
