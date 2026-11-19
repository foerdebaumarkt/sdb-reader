# The embedded file

## What it is

Some programs that suppliers write their safety data sheets with put a second
copy of the sheet's data into the PDF: a file in the exchange format eSDScom,
which is XML, a text format for programs. You do not see it when you open the
PDF. Most PDFs carry none.

`sdb-reader` reads the sheet from the printed text, always. Where a PDF
carries such a file, it is a second reading to check the first against.

## What `read` says about it

For a PDF with an embedded file, the record has a part `embedded_data`:

```json
{
  "format": "eSDScom",
  "filename": "sds.xml",
  "compared": true,
  "differences": [
    {"field": "hazard_codes", "embedded": ["H412"], "read": ["H315"]},
    {"field": "signal_word", "embedded": null, "read": "Achtung"}
  ],
  "version": "4.4.0",
  "system": "Example Author"
}
```

| Field | Meaning |
| --- | --- |
| `filename` | the embedded file's name |
| `version`, `system` | the version of the format, and the program that wrote the file |
| `compared` | `true` if the file could be read and the PDF is a German safety data sheet; otherwise there was nothing to compare |
| `differences` | the fields in which the embedded file and the sheet as read differ, each with both values; empty if they agree or nothing was compared |
| `unreadable` | for an embedded file that could not be read: the reason, as a message |

Compared are the date, the signal word, the pictograms, the codes of the H, P
and EUH statements, and the supplier's name and e-mail.

A difference says that the two disagree, not which is right. Look at the
printed sheet: either the supplier's system exported something else than it
printed, or the sheet was read wrongly.

## Getting the file out

`xml` hands out the embedded file unchanged, byte for byte:

```bash
sdb-reader xml sheet.pdf > sheet.xml
sdb-reader xml --save folder *.pdf
```

Without `--save` it takes one PDF and prints the file. With `--save` it takes
several and writes each PDF's file into the folder as `<name of the PDF>.xml`.
The folder has to exist, and a file that is already there is not overwritten.

| Exit code | Meaning |
| --- | --- |
| 0 | done; with `--save`, PDFs without an embedded file are named and skipped |
| 1 | the one PDF asked for has no embedded file, a file could not be handed out, a target already exists, or with `--save` not a single file was handed out |
| 2 | a path is not a file, the folder does not exist, or several PDFs were given without `--save` |

`xml` accepts `--lang` and `--messages` like `read`, for the lines it writes
on the error output.
