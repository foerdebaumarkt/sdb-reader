# Changelog

What changes for someone who uses the command or the library, newest first.
Versions follow the tags of this repository.

## Unreleased

## 0.9.0 – 2026-11-19

The first public version. What it offers:

- **The command `sdb-reader`.** `show` says what each PDF is and what it
  says, as a report to read; `read` gives the same as JSON, a record per
  file, described by a JSON Schema the package ships. Both take single files
  and whole folders. `xml` hands out the eSDScom file some PDFs carry, `ask`
  puts the sheets to a language model of your choice, and `diff` compares two
  runs field by field.
- **The library `sdb_reader`.** `read_sheet` reads a PDF: whether it is a
  German safety data sheet, and its product, supplier, dates, classification
  and label with the regulation's wording beside the sheet's. The library
  judges a sheet (`sheet_findings`, `requires_sheet`), chooses the current one
  among several (`current_state`), and stores a PDF's text so that a sheet can
  be read again without the file. The exported names are the interface;
  [What is promised](docs/api/stability.md) says what a program can build on.
- **No language model.** Reading is rules only and gives the same result for
  the same file every time. Only `ask` talks to a model, and only when called.
- **Languages.** It reads German sheets; a sheet in another language is
  recognised and not read. Messages come in German (the default) and English,
  and in any language through a catalog of your own.
- **Documentation.** At <https://foerdebaumarkt.github.io/sdb-reader/>, one
  edition per released version: the operator's manual in German and English,
  the guide to the library with a reference of every exported name, and how
  the reader works.
- **Python.** 3.12 to 3.15: every Python version still maintained.
- **Stage versions.** `EXTRACTION_VERSION` is 2 and `PARSER_VERSION` is 16.
  A text or a reading kept with other values is read again; later releases
  name every rise here, with what to do about what was kept.

Before 1.0 a minor version may break; a breaking change stands under
"Breaking" in its release's section.
