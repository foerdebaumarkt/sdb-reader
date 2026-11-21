# A reading and its parts

`read_sheet(path, *, max_pages=None)` returns a `SheetReading`. `max_pages`
bounds how many pages are read; by default all.

| Attribute | Type | Holds |
| --- | --- | --- |
| `verification` | `Verification` | what the file is, and why |
| `extraction` | `ExtractionResult` or None | the text read from the PDF; None where no text could be read |
| `parser_result` | `ParsedSheet` or None | the parsed sheet; set only for a German safety data sheet |
| `label_images` | `LabelImages` or None | the pictograms the label shows as pictures; set only where the label of a German safety data sheet was looked at |
| `warnings` | list of `Message` | that nothing was read further: `not-a-sheet` or `unreadable` |
| `errors` | list of `Message` | why no text could be read |

## What the file is

`reading.verification.kind` is a `DocumentKind`:

| Member | Value | The file is |
| --- | --- | --- |
| `SAFETY_DATA_SHEET` | `safety-data-sheet` | a German safety data sheet |
| `SAFETY_INFORMATION` | `safety-information` | laid out like one, without the title |
| `FOREIGN_SAFETY_DATA_SHEET` | `safety-data-sheet-other-language` | a safety data sheet in another language |
| `DOCUMENT` | `document` | anything else, or unreadable |

Only the first kind is parsed. The verdict also carries its own `warnings`
and `errors` as messages: the errors say why a file is no German safety data
sheet, the warnings what else stood out. `prints_statement_codes` says, for a
file that is neither a sheet nor a safety information, whether it prints at
least three different H, P or EUH codes. What the check weighed to reach its
verdict is not part of the reading.

```python
from sdb_reader import DocumentKind

verdict = reading.verification

assert verdict.kind is DocumentKind.SAFETY_DATA_SHEET
assert verdict.errors == []
assert [message.code for message in verdict.warnings] == ["short-sample"]
```

## The sheet

`reading.parser_result` has three attributes: `sheet`, a `SafetyDataSheet`,
`warnings`, the parser's messages, and `parts`, which is empty unless the
file holds [several sheets](#several-sheets-in-one-file).

| Attribute of `SafetyDataSheet` | Type | Holds |
| --- | --- | --- |
| `product_identifier` | str or None | the trade name from section 1.1 |
| `revision_date`, `issue_date` | `date` or None | the newest date of each kind the sheet names |
| `version` | str or None | the sheet's own version, as printed |
| `language` | str | `de` |
| `countries` | list of str | of `DE`, `AT`, `CH`; empty where the sheet names none |
| `stated_classification` | `StatedClassification` | what section 2 says: `CLASSIFIED`, `OLD_SYSTEM`, `NOT_CLASSIFIED`, `NOT_STATED` |
| `stated_voluntary` | bool | whether the sheet says of itself that it is issued voluntarily or that none is prescribed for its product |
| `stated_article` | bool | whether it calls the product an article, beside that sentence or by saying that as an article it needs no labelling |
| `hazard_statements` | `HazardStatements` | the label of section 2.2 |
| `contact_info` | `ContactInfo` | the supplier of section 1.3 and the emergency phone of 1.4 |
| `section_text` | dict of `Section` to str | the text of each section found |

```python
from sdb_reader import Section, StatedClassification

assert sheet.revision_date.isoformat() == "2024-03-12"
assert sheet.version == "3.1"
assert sheet.countries == []
assert sheet.stated_classification is StatedClassification.CLASSIFIED
assert sheet.section_text[Section.HAZARDS].startswith("Mögliche Gefahren")

label = sheet.hazard_statements
assert label.precautionary_codes == ["P102"]
assert label.supplemental_codes == []
assert label.pictograms == []
assert label.hazard_text == "H315 Verursacht Hautreizungen."

supplier = sheet.contact_info
assert supplier.supplier_name == "Muster GmbH"
assert supplier.supplier_address == "Musterweg 1, 12345 Musterstadt"
assert supplier.supplier_phone == "+49 555 0142-0"
assert supplier.supplier_email == "info@muster.example"
```

`ContactInfo.supplier_email` is the supplier's address, the first of its block.
`ContactInfo.information_email` is the address the sheet names for whoever
answers for it: the competent person's, else an information office's. It is
None where no such label stands at an address, as in this sheet; it may
equal `supplier_email`, and it may belong to a firm that wrote the sheet for the
supplier. Which of the two to use is the caller's to decide.

The pictograms are the ones the label names or shows as pictures
(`read_sheet` looks at the label as drawn). This sheet prints none. H315
calls for GHS07, but that is not in the reading: `clp_expected` gives it
([What the regulation expects](expected.md)). The label was looked at and
holds no red diamond, so `drawing_read` is true and the findings say the
pictogram was not found. `states_no_signal_word` and `states_no_pictograms`
say whether the label states it has none; this one states neither:

```python
from sdb_reader import Message, sheet_findings

assert label.drawing_read
assert not label.states_no_signal_word and not label.states_no_pictograms
missing = Message("pictogram-not-found", {"pictogram": "GHS07"})
assert missing in sheet_findings(sheet, reading.parser_result.warnings)
```

`read_sheet` also returns what it saw in the drawing as
`reading.label_images` (`LabelImages`), to keep beside the text
([Stored texts](stored-texts.md)).

## A file that is not a sheet, or cannot be read

Neither raises. A file that is something else has a kind and no parsed sheet:

```python
leaflet = path.with_name("leaflet.pdf")
with pymupdf.open() as document:
    document.new_page().insert_text((72, 72), "Produktinformation\nReinigt Fliesen.")
    document.save(leaflet)

other = read_sheet(leaflet)

assert other.verification.kind is DocumentKind.DOCUMENT
assert other.extraction is not None
assert other.parser_result is None
assert [message.code for message in other.warnings] == ["not-a-sheet"]
assert other.errors == []
```

A file no text could be read from has no text either, and `errors` says why:

```python
empty = path.with_name("empty.pdf")
with pymupdf.open() as document:
    document.new_page()
    document.save(empty)

unreadable = read_sheet(empty)

assert unreadable.verification.kind is DocumentKind.DOCUMENT
assert unreadable.extraction is None
assert unreadable.parser_result is None
# Text recognition read nothing, or tesseract is not installed.
assert unreadable.errors[0].code in {"no-text", "ocr-unavailable"}
assert [message.code for message in unreadable.warnings] == ["unreadable"]
```

## Several sheets in one file

Some files hold several complete sheets one after another: the parts of a
two-component product, the products of a combination pack, editions for
several countries. `parser_result.sheet` is then the file's reading with its
sheets united (every code any sheet prints, the stronger signal word, the
newest date), and `parser_result.parts` holds each sheet read on its own, in
the file's order. For a file that is one sheet `parts` is empty.

| Attribute of `SheetPart` | Type | Holds |
| --- | --- | --- |
| `sheet` | `SafetyDataSheet` | the sheet read from its own text, as a file holding only it would be |
| `warnings` | list of `Message` | what the parser noted about this sheet |
| `text` | str | the sheet's text; the parts joined by line breaks are the file's text without its cover page |

```python
from sdb_reader import extraction_from_dict, read_extraction


def component(name: str, revised: str, label: str) -> str:
    return (
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        f"Überarbeitet am: {revised}\n"
        "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
        f"Produktname: {name}\n"
        "ABSCHNITT 2: Mögliche Gefahren\n"
        f"2.2 Kennzeichnungselemente\n{label}\n"
        "2.3 Sonstige Gefahren\n"
        "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\n"
        "ABSCHNITT 16: Sonstige Angaben\n"
    )


kit = read_extraction(
    extraction_from_dict(
        {
            "text": component(
                "Harz",
                "20.07.2022",
                "Signalwort: Achtung\nH315: Verursacht Hautreizungen.",
            )
            + component(
                "Härter",
                "03.05.2021",
                "Signalwort: Gefahr\nH318: Verursacht schwere Augenschäden.",
            ),
            "extractor": "pymupdf",
            "pages_sampled": 2,
            "warnings": [],
        }
    )
).parser_result

assert kit.sheet.hazard_statements.hazard_codes == ["H315", "H318"]
assert kit.sheet.hazard_statements.signal_word == "Gefahr"

resin, hardener = kit.parts
assert resin.sheet.hazard_statements.hazard_codes == ["H315"]
assert resin.sheet.hazard_statements.signal_word == "Achtung"
assert hardener.sheet.hazard_statements.hazard_codes == ["H318"]
assert hardener.sheet.revision_date.isoformat() == "2021-05-03"
assert hardener.text.startswith("Sicherheitsdatenblatt")
```

Whether the united reading or one of the sheets is the one your program
needs, the library cannot tell: for the parts of one product the product
carries every label; for different products or editions in one file the
united reading can name hazards no single sheet names. `reading_to_dict`
gives the count as `sheet_count` and the single sheets as `parts`.

What the library can see, it says, and decides nothing by it:

- `sheet_findings(sheet, warnings, parts=parser_result.parts)` adds the
  finding `different-products` where the sheets' product names are not one
  product's, and `country-editions-differ` where one product's sheets for
  different countries differ (see [Judging a sheet](judging.md)). Without
  `parts` its result is as before.
- `parser_result.cover_page` is true where a cover page stands in front of
  the file's sheets: a page titled "Deckblatt", a kit's information sheet, a
  list of the set's sheets, a country's additions. It is no sheet; nothing
  of it is in `sheet`, in `parts` or in a part's `text`.
  `parser_result.display_term` is the word on it that names a display, as
  printed, or None.

```python
from sdb_reader import sheet_findings

assert kit.cover_page is False
assert kit.display_term is None
# Resin and hardener are the parts of one product: nothing to report.
assert "different-products" not in [
    finding.code for finding in sheet_findings(kit.sheet, kit.warnings, parts=kit.parts)
]
```

## A reading does not name its file

Nothing in a reading says which file it came from: the same content under
two names gives the same reading. Keeping the two together is your program's
part.

## Time, and files from anyone

A reading takes time in proportion to its file. The library reads a PDF of
up to 50 MB (`pdf-too-large` beyond), ignores lines of more than 2,000
characters (`line-too-long`, SDB-167) and ends a statement after 100 lines
(`statement-too-long`, SDB-168); the size of the text as a whole is not
bounded. A large file therefore takes long, most of it in reading the PDF.
Where files come from anyone, bound the files you accept by size and give
each reading a time limit of your own, for example by reading in a separate
process and ending it when the limit is reached.

## As JSON

`reading_to_dict` gives what `sdb-reader read` prints for a file, without the
`file` part, which names the file and is yours to add.

```python
import json

from sdb_reader import reading_to_dict

record = reading_to_dict(reading)

assert record["verification"]["kind"] == "safety-data-sheet"
assert record["sheet"]["sheet_required"] is True
assert [s["code"] for s in record["statements"]] == ["H315", "P102"]
assert [f["code"] for f in record["findings"]] == ["pictogram-not-found"]
assert json.dumps(record)  # plain JSON types throughout
```

| Parameter | Effect |
| --- | --- |
| `include_raw_text=True` | adds the text read from the PDF |
| `embedded=` | an `EmbeddedData` to compare with, see [Embedded data](embedded.md) |
| `catalog=` | the `Catalog` that words the messages; German without one, see [Messages and catalogs](messages.md) |

`sheet_to_dict(sheet, extraction)` gives only the `sheet` part, and
`verification_to_dict(verification, catalog=None)` only the verdict. The
shape of a record is described by [the JSON schema](schema.md).
