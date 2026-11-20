# Changelog

What changes for someone who uses the command or the library, newest first.
Versions follow the tags of this repository.

## Unreleased

### Changed

- **H360 and H361 keep the letters of their effect.** A label's `H360D`,
  `H360FD`, `H361fd` and the other codes of Annex VI of the CLP Regulation
  are read as such, letters as the regulation sets them (`H360DF` is
  `H360FD`, `H361D` is `H361d`); before, the code stood without its letters.
  A sentence that names one effect is that effect's code where the label
  prints no code, two effects together are the joined code, and the
  regulation's wording of a lettered code is the one of Annex VI. Pictogram
  and signal word do not change (SDB-155).
- **Precautionary statements printed as sentences only are read in the
  forms Annex IV of the CLP Regulation allows.** Where the label prints no P
  code and carries a hazard statement, a sentence that selects from a choice
  ("Schutzhandschuhe und Augenschutz tragen." is P280), fills in the
  supplier's detail for "…" or leaves out a part in brackets gives its code;
  before, only the regulation's exact wording did. Where two statements cover
  the same words, the longer one counts, H and EUH statements included; where
  two cover them alike, neither does, and the new message
  `precautionary-wording-unclear` names them. Never outside the label
  (SDB-163).
- **Codes printed with a space are read.** "H 315", "P 305 + P 351 + P 338"
  and "H 360 D" are the codes where they can be nothing else: the number is
  a statement of the regulation, the code opens its line or follows a list
  mark, "+", a colon, semicolon or comma, and the line's end, a separator,
  the statement's own first word or, at a line's start, the sheet's sentence
  follows. Measures, table values and names ("H 330 mm", "NOAEL P 250",
  "P 750") stay as they are. Before, only "EUH 208" was read this way
  (SDB-164).
- **`PARSER_VERSION` is 19** (0.9.0: 16). `EXTRACTION_VERSION` stays 2:
  stored texts are read again as they are; readings kept from before should
  be made again from them.

### Added

- **The message `label-line-unassigned`** names each line of a label that the
  parser assigned to nothing: no code, no signal word, no pictogram, no
  statement it read, no field name, no statement about the classification,
  no substance in the list that determines the label, no page furniture. It
  changes no reading; it shows where rules are missing (SDB-165).

- **P501 from its disposal sentence, also beside other P codes.**
  "Inhalt/Behälter gemäß lokalen/regionalen/nationalen/internationalen
  Vorschriften entsorgen." and the like (content and container, the
  supplier's detail, then "entsorgen" or "zuführen") are read as P501
  inside the label, where it carries a hazard statement and prints no P501
  code; the precautionary text keeps the sheet's sentence. "Leere Behälter
  können über den Hausmüll entsorgt werden." is no P501 (SDB-166).

### Fixed

Layouts and spellings from sheets outside the collection the reader was
measured on:

- A label that numbers its own parts on (`2.3 Gefahrbestimmende
  Komponenten`, `2.4 Gefahrenhinweise`) no longer ends at its "2.3"
  (SDB-156).
- A signal word behind its label counts where the label then says the
  diluted product needs none (SDB-157).
- No product name: an article number's label, a word for what the product is
  ("Gemisch"), the article number below stacked labels; "Bezeichnung des
  Stoffes oder des Gemisches:" is a name's label (SDB-158).
- The supplier behind "Name der Firma:", "Name des Herstellerunternehmens:",
  "Herstellerin", "Firmendetails:", "Company:", "Name oder Handelsname", and
  behind the colon of 1.3's heading; no street and no pointer as the name; a
  name cut from an address or a column glued to it; "BV", "NV" and "SA" as
  legal forms (SDB-159).
- "Abschnitt 7.3 angegeben" at the end of a sentence is no heading
  (SDB-160).
- Dates behind "Überarbei tung" broken over a line, with a weekday in front,
  and "Datum der Ausgabe:" as the issue date (SDB-161).
- A pictogram's code behind a statement and a page marker "Page n. 1 von 9"
  are not part of the statement's wording (SDB-162).

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
