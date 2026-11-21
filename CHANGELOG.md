# Changelog

What changes for someone who uses the command or the library, newest first.
Versions follow the tags of this repository.

## Unreleased

### Added

- **Whether the label prints a statement's code.** Each statement of the
  label says under `code_source` whether the sheet prints its code
  (`printed`) or only its sentence, to which the parser assigned the code
  (`from_wording`), and `hazard_statements.codes_from_wording` lists the
  assigned codes. The code lists stay as they are. `as_printed(text,
  codes_from_wording)` gives a statement text without the assigned codes,
  as the sheet prints it (SDB-174).
- **A hazard statement of the classification that the label does not
  carry.** Where section 2.1 names an H statement for the classification and
  the label carries neither its code nor its wording, the sheet gets the
  finding `hazard-statement-not-in-label` with the code. Not required are H400
  beside H410 and H318 beside H314 (CLP Annex III Part 1) and H304 on an
  aerosol (Annex I 1.3.3); not where the label carries no H statement at all,
  which `label-without-hazard-statement` says (SDB-173).
- **Findings for the label of a classified product.** Where section 2
  classifies the product under CLP and the label (2.2) is not found
  (`label-not-found`), carries no H statement
  (`label-without-hazard-statement`) or no P statement
  (`label-without-precautionary-statement`), the sheet gets a finding. The
  reading stays as the sheet prints it; nothing is added. Each finding says
  "not found": the sheet may lack it, or the parser may have missed it. Not
  for an article, a classification under the old law, or a label under the
  directives before CLP on a sheet dated before 1 June 2015; the parser notes
  such a label (`label-before-clp`) (SDB-169 to SDB-172).

### Fixed

- **A section heading numbered with a colon starts its section.** "3:
  Zusammensetzung / Angaben zu den Bestandteilen" is the heading of section 3
  as "3. Zusammensetzung …" is, when the title fits the number; before, section
  2 ran on into section 3, and an ingredient's classification counted as the
  product's (SDB-175).

### Changed

- **`PARSER_VERSION` is 20** (0.10.0: 19): findings are part of the reading.
  `EXTRACTION_VERSION` stays 2; readings kept from before should be made
  again from the stored texts.

## 0.10.0 – 2026-11-20

### Breaking

- **H360 and H361 keep the letters of their effect.** A label's `H360D`,
  `H360FD`, `H361fd` and the other codes of Annex VI of the CLP Regulation
  are read as such, letters as the regulation sets them (`H360DF` is
  `H360FD`, `H361D` is `H361d`); before, the code stood without its letters.
  A sentence that names one effect is that effect's code where the label
  prints no code, two effects together are the joined code, and the
  regulation's wording of a lettered code is the one of Annex VI. Pictogram
  and signal word do not change (SDB-155).
  A caller that compares codes with `H360` or `H361` has to take the
  lettered codes too.
- **`PARSER_VERSION` is 19** (0.9.0: 16). `EXTRACTION_VERSION` stays 2:
  stored texts are read again as they are; readings kept from before should
  be made again from them.

### Changed

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

- **The messages `line-too-long` and `statement-too-long`** name what the
  new bounds on a reading (see Security) left out: how many lines were too
  long and the length of the longest, and the codes a statement cut off
  after 100 lines begins with (SDB-167, SDB-168).

### Security

- **The embedded eSDScom file is read with `defusedxml`.** A document type,
  an entity or an external reference makes it unreadable
  (`embedded-doctype`), in any encoding. Before, the bytes were searched
  for "<!DOCTYPE" and "<!ENTITY", which a file in UTF-16 got past, and the
  standard library's parser expanded its entities. New dependency:
  `defusedxml` (Python Software Foundation License) (SDW-11).
- **Five patterns of the parser no longer slow down on long runs of blanks
  or dashes.** The revision date's label, the version line with its
  creation date, a classification given as a dash, a label without a signal
  word, and the substances before EUH208 read each character one way now; a
  crafted text of a few thousand blanks took them seconds before. The
  readings are the same.
- **Four more patterns no longer slow down on one long word.** The e-mail
  address, a display named on a cover page, an article number in front of a
  product's name and the addition at the end of a name start only where a
  run of their characters starts, or ask for the digit ahead; before, a run
  of some ten thousand letters or digits took seconds. The readings are the
  same.
- **A long run of capitalised words in a label no longer slows the reading
  down.** A classification entry in the label ("Skin Corr. 1, H314") is
  found by the last word of its class only; before, every capitalised word
  in front of it was tried, and a run of some twenty thousand characters
  took seconds. The codes read from the label are the same.
- **Five more places no longer slow down on a long run.** Lines of nothing
  but dashes or bullets above "Sonstige Gefahren", colons before "keine" or
  "N/A" in the classification, a long word before an article number's
  label, letters with full stops at the end of a supplier's name, and a run
  of brackets in a name's label were each read again from every character
  of the run; some twenty thousand characters took one to ten seconds. The
  readings are the same.
- **What a reading takes in is bounded.** A line of more than 2,000
  characters is not read (`line-too-long`), and a hazard, precautionary or
  EUH statement takes at most 100 lines (`statement-too-long`); the longest
  line of the sheets the reader was measured on has 837 characters, the
  longest statement 37 lines. A built text with a line of tens of thousands
  of dashes, or a statement followed by a hundred thousand lines that end
  nothing, took seconds to minutes; the bounds cover such cases whether or
  not anyone has found them. The text as read stays whole, so a kept text
  is read again as before (SDB-167, SDB-168).

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
