# Changelog

What changes for someone who uses the command or the library, newest first.
Versions follow the tags of this repository.

## Unreleased

### Breaking

- **The label is only the product's label.** A second label in 2.2, for a
  package of at most 125 ml, and a block under the Biocidal Products or the
  Detergents Regulation no longer add their codes, signal word, pictograms
  or sentences to `hazard_statements`; they stand apart under
  `further_labels` (below). On a set of about 13,000 sheets the label's
  codes, signal word or pictograms change on 6, which printed them only for
  the small package. `LabelImages` gives the pictograms below a small
  package's heading to that label (`small_packages`); label images stored
  at `LABEL_IMAGES_VERSION` 1 before this change have to be read from the
  PDFs again.
- **No finding for what a small package may leave out, where the sheet does
  not show the package.** Where a sheet prints no label for packages of at
  most 125 ml, its label may be one, and CLP Annex I 1.5.2.1 lets such a
  package leave out the hazard statements of some categories (H225, H226,
  H315, H319, H400, H410, H411 and others; acute toxicity 4 and STOT 2 and
  3 where not sold to the general public; never an aerosol's own elements,
  which Directive 75/324/EEC requires on every aerosol) and
  the precautionary statements of H362, H412 and H413. Such a statement is
  then no `hazard-statement-not-in-label`, and a label without hazard or
  precautionary statements whose hazards are all of that kind no
  `label-without-hazard-statement` or `label-without-precautionary-statement`
  (SDB-194). `clp_expected` then expects no signal word for H290 alone
  (1.5.2.1.3). On the same set 32 `hazard-statement-not-in-label` go, all
  H411 where the label prints H410 instead, and 1 of the other two.
- **No `euh-outside-label` for a treated article.** "Mit Konservierungsmittel
  … behandelte Ware. Kann allergische Reaktionen hervorrufen." is the
  sentence of the Biocidal Products Regulation, not EUH208, without
  "Enthält" (SDB-196). On the same set the finding goes from 4 sheets.

- **A sheet that has to be renewed anyway gets only the findings on its
  age.** Where a sheet was revised before 2021 (`predates-annex-ii`) or
  since then in the layout from before Regulation (EU) 2020/878
  (`old-format`), its findings are those on its age and those on a file of
  several sheets, no other (SDW-49). An undated sheet keeps all its
  findings. With it the exception for a label under the directives before
  CLP on a sheet dated before 1 June 2015 is gone: such a sheet gets no label
  finding anyway. The parser warning `label-before-clp` stays.
- **A date in the future is no date.** With the day of the run (`today`,
  which `read` passes), a revision or issue date after it stands in the
  record as `null`, for the file and for each of its sheets; before, it
  stood there as printed. The finding names it: `revised-in-future` the
  revision date, and the new `issued-in-future` the issue date. Before,
  `revised-in-future` named the issue date where the sheet had no revision
  date, and an issue date in the future beside a revision date went without
  a finding (SDB-137, SDW-34). The `SafetyDataSheet` of the library keeps
  the date as read.
- **The label only as printed.** `signal_word` and `pictograms` hold what the
  label prints, and nothing derived from its codes any more (SDB-169).
  Where the label says nothing about a signal word, `signal_word` is now
  empty (SDB-176). `pictograms` holds the codes the label's text names and,
  new, the pictograms it shows as pictures, read from the PDF (SDB-179); a
  printed pictogram that Article 26 CLP would leave out stays. The parser
  warnings `signal-word-derived` and `pictograms-derived` are gone. A caller
  that needs what the codes call for asks `clp_expected` (below).
- **`read_extraction` without the pictures** gives only the pictograms the
  text names. A caller that keeps texts keeps the pictures beside them
  (`label_images_to_dict`) and passes them back; see "Keeping texts".
- **`PARSER_VERSION` is 21** (0.11.1: 20); a record of a file with several
  sheets also carries new keys. `EXTRACTION_VERSION` stays 2:
  stored texts stay valid, but the pictures have to be read from the PDFs
  once, about a tenth of a second per sheet; readings kept from before
  should be made again.

### Added

- **The findings `signal-word-conflicts` and
  `small-package-signal-word-conflicts`** (`printed`, `expected`): a label
  prints "Achtung" where a code of the product calls for "Gefahr" whatever
  its category, or "Gefahr" where no code can call for it (SDB-199). The
  reading stays as printed; either side may be wrong. On a set of about
  13,000 sheets: 2, the small-package labels of an oxygen product.
- **An aerosol keeps its own elements on a small package** (SDB-198):
  Directive 75/324/EEC, to which CLP Annex I 1.5.2.1.1 refers, requires the
  signal word, GHS02, H222/H223 and H229 on every aerosol dispenser.
  `clp_expected(..., small_package=True)` no longer leaves them out.
- **`further_labels`** under `hazard_statements`, with `FurtherLabel` and
  `LabelKind`: each block of 2.2 beside the label, with its `kind`
  (`small-package`, `biocides`, `detergents`), its `heading` and `text` as
  printed, the `omitted_codes` of a sentence that says what a small package
  leaves out, and for a small package's label its `label`, read like a label
  and from its own drawing (SDB-188 to SDB-190, SDW-51).
- **`condition`, `condition_text` and `statement_conditions`** under
  `hazard_statements`, with `LabelCondition`: whom the label says it applies
  to ("Obige Kennzeichnung gilt bei Abgabe an privaten Endverbraucher."), and
  single statements printed with a condition ("Nur für private
  Endverbraucher: P101 …", EUH210 for packages not meant for the general
  public), as printed; the statements stay in the label (SDB-191, SDB-192).
  All new keys are optional in the schema, and `sheet_from_dict` reads
  records without them.
  A small package's label counts for whether the product needs a sheet
  (SDB-76).
- **The findings `small-package-hazard-statement-not-in-label`,
  `small-package-signal-word-not-found` and
  `small-package-pictogram-not-found`**: what a small package's label lacks
  that CLP Annex I 1.5.2.1 requires there too, only for the elements the
  label speaks of (SDB-193). `clp_expected(label, small_package=True)`
  judges such a label.
- **The finding `hazard-statement-not-classified`**: the label prints a
  hazard statement the classification in 2.1 does not name, with the
  printed code and the codes 2.1 names; either the classification or the
  label may be the wrong one (SDB-197). The size of the package does not
  matter. On a set of about 13,000 sheets it names 51: 32 that print H410
  where 2.1 classifies Aquatic Chronic 2, and 12 that print it over Chronic
  3. A small package's label is held to the pictograms and signal word of the
  product's codes (2.1, the label and its own), not only its own; H304 of an
  aerosol does not count.
- **No H304 finding where the sheet names a sealed spray attachment** or
  Annex I 1.3.3 CLP as the reason to leave the aspiration hazard out
  (SDB-195).

- **`clp_expected(label)` and `ClpExpected`** (BIB-25): the signal word the
  label's H and EUH codes call for, the pictograms its H codes call for with
  the precedence of Article 26, and where the reading differs from them, as
  data. The signal word never follows from the pictograms. Use it to fill a
  gap or to check a label; see "What the regulation expects".
- **`clp_expected` in the record of `read`**, for the file and for each
  entry of `parts`: what `clp_expected` returns, beside the reading and not
  in it. Optional in the schema, so records written before stay valid
  (SDW-48).
- **A third stage for the label's drawing:** `read_label_images`,
  `LabelImages`, `LabelImagesStatus`, `label_images_to_dict`,
  `label_images_from_dict`, `LABEL_IMAGES_VERSION` (1) and
  `label_images_stage()` (BIB-24). It finds the label on the pages, looks
  for red-framed diamonds and names each by its likeness to references made
  from the public-domain drawings of the nine pictograms; no model, no new
  dependency. `SheetReading.label_images` holds what `read_sheet` saw.
- **`drawing_read`, `states_no_signal_word` and `states_no_pictograms`**
  under `hazard_statements`: whether the label was looked at as drawn, and
  whether it states it has no signal word or no pictogram ("Signalwort
  entfällt", "Gefahrenpiktogramme: keine"). A reading stored before reads
  back without them (SDB-179, SDB-180, SDW-47).
- **The finding `signal-word-not-found`** with the expected word: the codes
  call for a signal word and none was found printed (SDB-178).
- **The findings `pictogram-not-found`, `pictogram-not-expected` and
  `pictogram-precedence`** (SDB-181), and the warnings
  `label-images-not-read` (with `reason`: `no-text-layer`,
  `no-label-region`, `labels-not-paired`) and `pictograms-not-recognised`
  (with `count`).
- None of these findings says something was not found where the label
  states it has none; `pictogram-not-found` comes only where the drawing was
  read. A finding comes only where the library is sure the sheet deviates
  (SDB-183): GHS04 is never expected, which Article 33 CLP lets the
  transport label of a gas cylinder replace, and GHS05 not where H290 is
  its only reason, which Annex I 1.3.6 makes optional on a package for
  consumers; printed, neither is a finding. No finding for an article or a
  classification under the old law.
- **The oldest sheet of a file.** For a file with several sheets, `read`
  names under `oldest_sheet` the sheet with the oldest date (its number,
  the date, and whether it is the revision or the issue date), and `show`
  names it under "Die Datei als Ganzes". The file's reading still carries the
  newest date the file names, so a file that holds a hardener from 2014
  beside a new resin was not reported as old; which sheet's date counts is
  for the user to decide.
- **Findings on each sheet's age.** Each entry of `parts` carries
  `findings`: `revised-in-future`, `undated`, `predates-annex-ii` and
  `old-format`, judged on that sheet's own dates. `show` lists them with the
  sheet's notes. The file's findings stay as they were. Both keys are
  optional in the schema, so records written before stay valid.

### Changed

- **No `pictogram-not-expected` for GHS08 on an aerosol.** Annex I 1.3.3
  CLP lets an aerosol leave out the aspiration hazard, and GHS08 may stand
  for it where the label leaves out H304, so the library is not sure the
  sheet deviates (SDB-181, SDB-183). An aerosol is what SDB-173 takes for
  one: "Aerosol 1" to "3" in section 2, or H222, H223 or H229.
  `clp_expected` is unchanged and still lists GHS08 as not expected. On the
  same set the finding goes from 2 sheets.
- **`wording-deviates` only where the sheet really deviates.** A statement
  is no longer reported where the sheet prints a wording an earlier
  consolidated version of the CLP Regulation gave it, a combination as the
  wordings of its parts one after the other, each part as it reads alone or
  inside the combination (P351 alone says "ausspülen", inside
  P305+P351+P338 "spülen"; a sheet may mix the two), or a part in square
  brackets left out or given with a slash ("abwaschen/duschen"). Case,
  punctuation and spacing still do not count. On a set of about 13,000
  sheets, of those not due for renewal the finding drops from 698 sheets to
  16. Articles and auxiliaries ("der", "die", "das", "ist", "sind") may be
  left out or added, and an infinitive may carry "zu" ("einzuhalten" for
  "einhalten"); every other word must stand, a negation exactly as in the
  regulation, so "Darf in die Hände …" still deviates. That takes the
  finding off 12 more of those sheets. The earlier wordings come with
  the package (`clp_earlier_wordings_de.json`, from 29 consolidations since
  December 2010) and are made by `tools/clp/earlier_wordings.py` (SDW-50).
- **The proposed rule to date a file by its oldest sheet is withdrawn.**
  The file's reading keeps the newest date; the oldest sheet stands beside
  it instead.

### Fixed

- **Pictograms printed above the label's heading** belong to the label.
  Where a sheet sets "Gefahrenpiktogramme" and nothing but the codes
  directly above "2.2 Kennzeichnungselemente", the codes are read and the
  drawing is looked at from that line (SDB-187). On a set of about 14,500
  sheets 3 readings gain their pictograms and lose `pictogram-not-found`.
- **A second line naming the label elements starts no second label in the
  drawing.** "Kennzeichnungselemente (CLP):" under "2.2.
  Kennzeichnungselemente", or "ergänzende Kennzeichnungselemente" further
  down, is a line of the same label; only another heading numbered 2.2
  starts one, as the text's label runs to its end (SDB-179, SDB-4). A file
  of two sheets so printed found four labels in its drawing and gave neither
  sheet its pictograms (`labels-not-paired`); on the same set 10 such files
  now read each sheet's drawing. `LABEL_IMAGES_VERSION` stays 1, unreleased:
  label images kept from this stage before should be read again.
- **Statement texts read through a label's column.** A heading of the
  label set between a statement's lines ("EUH Sätze", "Sicherheitshinweise")
  no longer cuts the statement short, a cell of the classification table
  read into a statement is dropped where the label prints the statement
  whole, and a misprinted code mark left alone ("EU208 -") goes (SDB-184 to
  SDB-186). On a set of about 13,000 sheets 8 readings change, all to the
  sheet's wording, and 3 `wording-deviates` findings go.
- **A date in the future no longer leaves a file of several sheets
  undated.** Each of its dates is the newest one of its sheets names that is
  not in the future (SDB-182).
- **A signal word with an exclamation mark behind its label** ("Signalwort:
  Achtung!") is read; only a sentence that goes on after the mark on the
  same line is the opening of EUH211 or EUH212 (SDB-176).

## 0.11.1 – 2026-11-21

A documentation release: the README answers why one would not just give a
PDF to a language model, and "How it works" sets out the philosophy behind
the reader. The code is that of 0.11.0; `PARSER_VERSION` stays 20. The
documentation site gets the edition of 0.11.0, which its release did not
deploy, together with this one.

### Documentation

- **Why written rules and not a language model.** The README (English and
  German) answers why one would not just give a PDF to a language model,
  with what a test on difficult sheets showed about current models, and
  "How it works" explains the reasons in a section of its own.
- **The philosophy behind the reader.** "How it works" opens with the
  principles the reader follows: read what is printed, report and do not
  correct, leave the decision to the user, better missing than invented; the
  README points to them.
- **The specs** keep their withdrawn rules in `specs/historie.md`, and
  `specs/README.md` says how a rule is written.

## 0.11.0 – 2026-11-21

This release reads the label strictly as the sheet prints it and reports,
separately, where it falls short of the CLP Regulation: a classified product
without a label, without hazard or precautionary statements, or without a
hazard statement its classification names. Some sheets print a statement's
wording without its code; the reading now says which codes the sheet prints
and which the parser assigned from the wording, so a user can show the label
exactly as printed. `PARSER_VERSION` rises to 20.

### Breaking

- **`PARSER_VERSION` is 20** (0.10.0: 19): findings are part of the reading.
  `EXTRACTION_VERSION` stays 2; readings kept from before should be made
  again from the stored texts.

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

## 0.10.0 – 2026-11-20

This release makes the reader more exact on sheets from many sources and
harder to slow down: H360 and H361 keep the letters of their effect,
precautionary statements printed as sentences are read in the forms the CLP
Regulation allows, codes printed with a space are read, and lines of the label
the parser assigns to nothing are named. Eight reading errors found on sheets
from outside the original collection are fixed, an embedded eSDScom file is
parsed safely, and what a reading takes in is bounded. `PARSER_VERSION` rises
to 19.

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
