# Keeping texts

## Why

Reading a PDF's text takes nearly all the time of a reading, and text
recognition takes seconds per page. Judging and parsing the text takes
milliseconds. A program that reads many sheets keeps each text and reads
from it again when a newer parser arrives, without touching the PDFs.

## Store a text and read from it

`extract_pdf_text` reads only the text. `extraction_to_dict` gives it in a
form to store as JSON, `extraction_from_dict` reads that back, and
`read_extraction` gives the reading `read_sheet` would give for the file.

```python
import json

from sdb_reader import (
    extract_pdf_text,
    extraction_from_dict,
    extraction_stage,
    extraction_to_dict,
    read_extraction,
    reading_to_dict,
)

stored = extraction_to_dict(extract_pdf_text(path, max_pages=None))
kept = json.dumps(stored)  # store this beside your record of the file

# Later, without the PDF:
stored = json.loads(kept)
again = read_extraction(extraction_from_dict(stored))

assert reading_to_dict(again) == reading_to_dict(reading)
```

One thing differs from `read_sheet`:

- `extract_pdf_text` raises `ExtractionError` for a file it cannot read;
  `read_sheet` catches that and returns a reading with `errors`. The error's
  `message` attribute is the `Message` with the reason.

Like `read_sheet` it reads all pages unless `max_pages` says otherwise.
With `ocr=False` a PDF without a text layer is not handed to text
recognition: the call fails with the reason `no-text-layer` instead.

```python
from sdb_reader import ExtractionError

try:
    extract_pdf_text(path.with_name("missing.pdf"))
except ExtractionError as error:
    assert error.message.code == "pdf-not-found"
```

A stored text holds the text, how it was read (`extractor`), how many pages
were read (`pages_sampled`), the warnings as codes and values, and the stage
it comes from:

```python
assert sorted(stored) == ["extractor", "pages_sampled", "stage", "text", "warnings"]
```

A text that text recognition read, in whole or for single pages, also holds
`tesseract`: the version of the program that read it. That version is not
part of the stage, because it concerns scans only and differs from machine to
machine. If the same scan must give the same text everywhere, compare it with
the version on the machine that reads next, and read the PDF again where they
differ.

## When what you kept is out of date

The library reads in two stages, and each has a version, a whole number that
only ever rises:

| Name | Rises when | What to do |
| --- | --- | --- |
| `EXTRACTION_VERSION` | the same PDF can give another text | read the PDF again |
| `PARSER_VERSION` | the same text can give another reading | read again from the stored text |

Store both numbers with every reading you keep, and compare them with the
library's when you start.

The text depends on the PDF library too. `extraction_stage()` names the
reading stage's version together with the PDF library's, and a stored text
carries that value as `stage`. A stored text holds only while its `stage` is
the current one:

```python
from sdb_reader import EXTRACTION_VERSION, PARSER_VERSION

assert stored["stage"] == extraction_stage()
assert stored["stage"].startswith(f"{EXTRACTION_VERSION}+pymupdf-")
assert isinstance(PARSER_VERSION, int)
```

The library's part of the value is the version of the module `pymupdf`,
whichever distribution installed it (the package depends on `pymupdf-lite`).

A text of another stage is read all the same; whether to use it is yours to
decide by comparing. A text stored by an earlier version of the library can
always be read back: a warning in a form this version does not know is kept
as the message `unknown`.

[CHANGELOG.md](../../CHANGELOG.md) says for every release whether a version
rose.
