# Embedded data

Some authoring systems embed their own export of the sheet in the PDF, a
file in the exchange format eSDScom. It is a second reading to check
against; the sheet's data always come from the printed text.

## Reading it

`read_embedded(path)` gives the first embedded eSDScom file of a PDF as an
`EmbeddedData`, or None for a PDF without one. Most PDFs carry none:

```python
from sdb_reader import read_embedded

assert read_embedded(path) is None
```

| Attribute of `EmbeddedData` | Holds |
| --- | --- |
| `filename` | the embedded file's name |
| `content` | its bytes, unchanged; None for a file the library refuses to hand on |
| `sheet` | what it says, as an `EmbeddedSheet`; None where it could not be read |
| `unreadable` | the reason it could not be read, as a `Message`; None otherwise |

`parse_embedded(name, content)` reads a file that was taken out of its PDF
before, for instance with `sdb-reader xml`:

```python
from sdb_reader import parse_embedded

feed = (
    b"<DatasheetFeed><Datasheet><HazardIdentification><HazardLabelling>"
    b"<ClpLabellingInfo><ClpHazardStatement><PhraseCode>412</PhraseCode>"
    b"</ClpHazardStatement></ClpLabellingInfo></HazardLabelling>"
    b"</HazardIdentification></Datasheet></DatasheetFeed>"
)
embedded = parse_embedded("sds.xml", feed)

assert sorted(embedded.sheet.hazard_codes) == ["H412"]
assert embedded.unreadable is None
assert parse_embedded("other.xml", b"<other/>").unreadable.code == "embedded-wrong-root"
```

An `EmbeddedSheet` carries `format_version`, `authoring_system`, `date`,
`signal_word`, `pictograms`, `hazard_codes`, `precautionary_codes`,
`supplemental_codes`, `supplier_name` and `supplier_email`.

A file that is too large, carries a document type declaration, is not
well-formed XML or is no eSDScom file is not read; `unreadable` says which.

## Comparing it with the sheet as read

`embedded_differences(embedded_sheet, sheet)` lists the compared fields in
which the two differ, each as an `EmbeddedDifference` with `field`,
`embedded` and `read`:

```python
from sdb_reader import embedded_differences

differences = embedded_differences(embedded.sheet, sheet)
by_field = {difference.field: difference for difference in differences}

assert by_field["hazard_codes"].embedded == ["H412"]
assert by_field["hazard_codes"].read == ["H315"]
```

Compared are the date, the signal word, the pictograms, the codes of the H,
P and EUH statements, and the supplier's name and e-mail.

`reading_to_dict(reading, embedded=...)` adds the comparison to the record
as `embedded_data`, with `compared` saying whether there was anything to
compare:

```python
record = reading_to_dict(reading, embedded=embedded)

assert record["embedded_data"]["compared"] is True
assert {d["field"] for d in record["embedded_data"]["differences"]} >= {"hazard_codes"}
```
