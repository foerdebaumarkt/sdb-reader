# Changelog

What changes for someone who uses the command or the library, newest first.
Versions follow the tags of this repository.

The headings of a release say what it asks of a caller:

- **Breaking**: code that uses the library or the command has to change,
  because an exported name, a message code or its values, the JSON schema,
  or an option or exit code of the command line changed.
- **Read again**: a stage version rose. No code has to change, but texts or
  readings kept from before are outdated and have to be made again.
- **Added**, **Changed**, **Fixed**: what else a caller may notice, such as
  what the same file now reads as.

Up to 0.15.0 the rise of a stage version and a changed reading stand under
"Breaking" too.

## Unreleased

### Read again

- **`PARSER_VERSION` is 26** (0.16.0: 25): the hazard text of a label that
  prints its H sentences without codes is those sentences. Readings kept
  from before should be made again from the stored texts;
  `EXTRACTION_VERSION` stays 2.

### Fixed

- **A label that prints its H sentences without codes gets them as its
  hazard text.** Where 2.1 prints the codes ("H411 Aqu. chron. Kat. 2 –
  …"), the hazard text was 2.1's line and what followed it, or only the
  codes, and codes of the label could be missing from it (SDB-6).

## 0.16.0 – 2026-11-27

This release is about a label that names codes without their sentences.
Where section 16 writes those sentences out, the reading now carries them,
as the sheet prints them, and `with_section_16` puts them beside their
codes. Rows of codes left from 2.1 no longer stand beside the label's own
sentences, and a label behind a reference to section 16 is read again.
Readings kept from 0.15 should be made again; the stored texts stay valid.

### Read again

- **`PARSER_VERSION` is 25** (0.15.1: 24): a reading now carries the
  sentences of section 16 for codes the label prints without one, and a
  row of codes left from 2.1's table goes where each of its codes has its
  sentence, and a reference ending on a section's number opens no section.
  `EXTRACTION_VERSION` stays 2; readings kept from before should
  be made again from the stored texts.

### Added

- **The sentence section 16 prints for a code the label prints without
  one.** Some labels print only codes ("P102, P314, P405, P501") and write
  the sentences out in section 16. `hazard_statements.section_16_wordings`
  gives, for each code the statement texts name without a sentence, the
  first sentence section 16 prints under exactly that code, as printed;
  the statement texts stay as the label prints them.
  `with_section_16(text, wordings)` gives each such code a line of its own,
  with its sentence where section 16 has one (SDB-222). The key is optional
  in the schema, so records written before stay valid.

### Fixed

- **A reference that ends on a section's number opens no section.** A
  line "Abschnitt 16." (or "Abschnitt 13") under a sentence that breaks
  off after a lower-case word ("… finden sich unter", "Entsorgung: siehe")
  ends that sentence; it began the section it names, and the text after it
  went there. With the title or a subsection of its section below it, it
  is still a heading (SDB-21). On one sheet the label was read as section
  16 and no statement text was found.
- **A row of codes from 2.1 no longer stands in the hazard text beside
  the label's sentences.** Where 2.1 prints its codes in a column and the
  label prints each of them with its sentence, a code in a combination
  ("H302+H332 - Gesundheitsschädlich …") and a code with text behind it
  ("H373 (Blut)") included, the row goes, down to a single code left of
  it; before, it stayed whenever 2.1 also named a code the label does not
  carry (SDB-52). Only lines of codes alone go; no code
  list changes.

### Documentation

- **A page whose text layer interleaves two columns is not supported.**
  Troubleshooting says so: the codes are read, the sentences may not be.
  The two open questions on it in the spec are closed.
- **The changelog tells a new reading from a breaking change.** The rise
  of a stage version now stands under "Read again": no code has to
  change, kept texts or readings have to be made again. "Breaking" is
  left for what breaks a caller's code (What is promised, Releasing,
  Stage versions).

## 0.15.1 – 2026-11-26

This release takes a dependency out: the eSDScom file a PDF may carry is
read without `defusedxml`, a package that has had no finished release since
2021. What the reader reads and refuses stays the same, and so do the stage
versions: texts and readings kept from 0.15.0 remain valid.

### Changed

- **One dependency fewer: `defusedxml` is gone.** The embedded eSDScom
  file is read with Python's own XML parser, which stops at a document
  type declaration. Nothing changes in what is read or refused: a document
  type, an entity or an external reference still makes the file unreadable
  (`embedded-doctype`), in any encoding (SDW-11). The last finished
  release of `defusedxml` is from March 2021. The package now installs
  two others, `pymupdf-lite` and `structlog`.

### Documentation

- **Releasing** begins with a look at what the package installs: when
  each dependency was last released. No check notices a package that
  nobody maintains any more.

## 0.15.0 – 2026-11-25

This release gives the label of a small package its sentences: where a sheet
prints that label as bare codes, each code now carries the sentence the
sheet's own label prints for it. The rules of the reading are set out anew,
by subject. Readings kept from 0.14.0 have to be made again.

### Breaking

- **`PARSER_VERSION` is 24** (0.14.0: 23). Readings kept from 0.14.0
  should be made again; stored texts and label images stay valid.

### Fixed

- **A small package's label gives each statement its sentence** (SDB-188).
  Where that label prints its codes bare or in a row, such as "H314-H335",
  each code now stands on its own line with the sentence the sheet's label
  prints for it; a combination stays one code, and a sentence the small
  package's label prints itself comes first. Its codes are unchanged. On
  about 14,850 sheets the small package's label of 20 changes, and nothing
  else does.

### Documentation

- **The rules stand under headings by subject** (`specs/sicherheitsdatenblatt.md`),
  in the order a sheet is read, and each begins with what holds. A rule that
  only added a case to another is taken into the rule of its subject, so 35
  rule numbers now point to another rule; `specs/historie.md` says which,
  with the old text. What the library does is unchanged.

## 0.14.0 – 2026-11-25

This release narrows which EUH statements say that a product needs a safety
data sheet, after a check against the consolidated texts of REACH and CLP:
only EUH210 and the statements of a sensitising substance still do. Readings
kept from 0.13.0 have to be made again.

### Breaking

- **`PARSER_VERSION` is 23** (0.13.0: 22). Readings kept from 0.13.0
  should be made again; stored texts and label images stay valid.
- **Fewer EUH statements say that a product needs a sheet** (`sheet_duty`,
  SDB-220). Only EUH210 and the statements of a sensitising substance,
  EUH208, EUH204 and EUH205, still do, as REACH Article 31(3) owes a sheet
  on request for such a mixture; these three now also go before a sheet that
  calls itself voluntary. EUH066, EUH401, EUH211, EUH212 and EUH202 alone no
  longer do. On a set of about 12,800 sheets 364 no longer need a sheet and
  6 do; `old-format` goes where the product no longer needs one.

## 0.13.0 – 2026-11-25

This release reads the label more fully and gives it out more carefully.
It finds more pictograms as pictures: in black and white or grey, drawn in
strips, on scanned pages and below a page's head, and it tells the flame
from the flame over circle. Each pictogram says whether the label prints
its code, its picture or both. The reading tells three kinds of sheet
apart. A sheet of the rules before June 2017 is read without its label,
and whether its product needs a sheet is "not checked". A sheet from then
on is read in full with every finding. A label that surely lacks what it
must show is withheld with an error unless the caller asks for it, so that
no program shows a hazardous product without its warnings by mistake.
Readings and label images kept from 0.12.0 have to be made again.

### Breaking

- **`LABEL_IMAGES_VERSION` is 2 and `PARSER_VERSION` is 22** (0.12.0: 1 and
  21). Label images kept from 0.12.0 have to be read from the PDFs again
  (`read_label_images`, about a tenth of a second per sheet, a second per
  scanned page); readings kept from before should be made again.
  `EXTRACTION_VERSION` stays 2: stored texts stay valid.
- **A label that surely lacks what it has to show is withheld** unless asked
  for: where the reading carries `pictogram-not-found`,
  `signal-word-not-found`, `label-without-hazard-statement`,
  `label-not-found`, `hazard-statement-not-in-label` or
  `pictograms-not-recognised`, `read_sheet` and `read_extraction` return it
  with the error `label-incomplete` and an empty `hazard_statements`;
  `accept_incomplete_label=True` (`--accept-incomplete-label` for `read` and
  `show`) gives it as printed, with its findings (SDB-217, BIB-26). So no
  program shows a hazardous product without its warnings by mistake.
- **The label of a sheet of the rules before June 2017 is not read**
  (revised, or else issued, by 31 May 2017, or classified or labelled under
  Directives 67/548/EEC or 1999/45/EC): `hazard_statements` is empty and
  `label_withheld` says `before-2017-06` (SDB-216). New in the sheet and its
  record: `label_withheld`.
- **A sheet due for renewal whose label is read gets all findings**, no
  longer only those on its age: revised from June 2017 to 2020, or in the
  format before 2020/878 (SDW-49). On a stock of 11,529 sheets that is 44
  findings more.
- **`requires_sheet` is `sheet_duty`** and answers with a `SheetDuty`:
  `required`, `not-required` or `not-checked`, not checked under the rules
  in force (SDB-218). A sheet of the rules before June 2017 is always
  `not-checked`, since a sheet of the transition may classify one way under
  the old directives and another under CLP; a withheld incomplete label is
  `required` where section 2 classifies the product, else `not-checked`.
  The record's `sheet.sheet_required` (a boolean) is `sheet.sheet_duty` (one
  of the three), and `show` says "not checked under the rules in force".
- **Pictograms above the label's heading are no longer the label's.** The
  rule of 0.12.0 that a block of pictograms directly above "2.2
  Kennzeichnungselemente" belongs to the label (SDB-187) is withdrawn: such a
  block stands in 2.1. Where the label then shows no pictogram, the reading
  has none and `pictogram-not-found` names the sheet's error (SDB-209).

### Changed

- **An EUH wording in running text outside the label is not reported**
  (`euh-outside-label`): a sentence that follows other words on its line
  describes an effect (SDB-219). One that begins its line, or follows its
  code, is still reported.

### Added

- **`pictogram_forms`** in a label (`HazardStatements`) and in the record of
  `read`: how the label prints each pictogram, `code` where its text names
  it, `picture` where its drawing shows it, or both (SDB-211). A picture in
  2.1 does not count. Missing in readings stored before.

### Fixed

- **Black-and-white and grey pictograms** are found as pictures, as REACH
  Annex II 2.2 allows them on a safety data sheet (SDB-212).
- **The flame (GHS02) and the flame over circle (GHS03)** are told apart by
  the ring under the flame, so a flame drawn broad and round at its foot is
  no longer left unnamed (SDB-213). On a set of about 14,500 sheets the
  picture of 6 labels changes (3 grey, 3 flames); one reading gains a
  pictogram, GHS02, the others had it from its code already.
- **A heading numbered 2.2 that begins with "Kennzeichnung" or "Etikett"
  begins the label** ("2.2 Kennzeichnung nach GHS:", "2.2 Kennzeichnung des
  Gemischs nach CLP-Verordnung", "2.2. Etiketteninhalt"), in the text and in
  the picture;
  where a sheet prints the label under two such headings, it runs from the
  first (SDB-209).
- **A classification named in a clause of a condition** ("… selbst wenn sie
  … als gefährlich eingestuft wurden") is no classification, and "eine
  Einstufung … ist nicht nötig" says the product is not classified (SDB-214).
- **A pictogram drawn otherwise than the reference but clearly most like it**
  is named, as an environment pictogram (GHS09) at a likeness of 0.35 with
  the next 0.13 behind (SDB-215). On a set of about 14,850 sheets 3
  readings change, all of sheets from manufacturers' websites: one gains
  GHS05 and GHS07, one GHS09, one is read as not classified; three wrong
  findings go.
- **A sentence behind a printed code stays with that code.** "P502
  Inhalt/Behälter der Problemabfallentsorgung zuführen." is P502 as printed,
  no longer P502 and P501 (SDB-210). On a set of about 14,500 sheets 6
  readings change: 3 lose the pictograms above "2.2" and get
  `pictogram-not-found`, 2 read P502 without P501, one finds its label and
  with it GHS07.

- **Pictograms where the label was not found as a picture.** A label headed
  "GHS-Kennzeichnung" instead of "Kennzeichnungselemente" is a label, in the
  text and in the picture; where no label is found, the pictograms section 2
  shows count. Where the label is found only its own count: a pictogram in
  2.1 belongs to the classification, which the label may leave out under
  Article 26 CLP (SDB-202).
- **Scanned sheets** have their label found on the page pictures by the
  positions of the words text recognition reads, and its pictograms read
  (SDB-204). Without text recognition `label-images-not-read` says
  `no-text-layer`, as before.
- **A pictogram code misread by text recognition** with more zeros or a space
  ("GHS007", "GHS 05") is read as the code it is (SDB-203).
- **A page's head and foot are no part of the label.** Where the label runs
  on to the next page its picture is read below that page's head and above
  its foot, so a red logo in the head is no unrecognised pictogram (SDB-205).
- **A pictogram embedded as a picture on the label's next page** is no
  longer lost: reading that page's lines with their images made PyMuPDF
  render it without them afterwards (SDB-205).
- **Pictograms drawn from thin strips of a picture,** whose red frame has
  gaps of a pixel, are found; touching pictograms are each cut to their own
  frame (SDB-208). **A page without a text layer** in a file whose other
  pages have one has its label found by text recognition too (SDB-204).
- **Small pictograms** that the first look names none of are looked at again
  in finer detail (SDB-206). Checked against the codes 4,022 pictograms carry
  below them on a set of about 14,500 sheets: none is named otherwise than
  its code says.

On that set 9 sheets gain pictograms, each one their H statements call for,
none loses one; on 271 the label's picture is now read, and 29 lose a wrong
`pictograms-not-recognised`. The orange symbols of Directive 67/548/EEC are
still not taken for pictograms, on purpose (SDB-207).

### Documentation

- **What it handles** (German: Was es abdeckt): one page, without technical
  terms, on what the reader does, for readers new to safety data sheets.

## 0.12.0 – 2026-11-24

This release reads the label strictly as printed, pictures included, and
reports a deviation from the CLP Regulation only where it is certain. The
pictograms are those the sheet prints, as codes or as pictures read from
the PDF in a third stage, and what the codes call for comes from
`clp_expected`. A second label in 2.2, for a package of at most 125 ml or
under the Biocidal Products or the Detergents Regulation, stands apart
under `further_labels`, with the conditions the sheet prints. Where a
finding depends on what the sheet does not say (the package, its size, who
buys it), there is none; a sheet due for renewal gets only the findings on
its age, and a date in the future is no date. New findings name a label
statement the classification does not, a signal word that conflicts with
the codes, and what a small package's label lacks. `PARSER_VERSION` rises
to 21; the label's pictures have to be read from the PDFs once. 0.11.1 was
not released: its documentation is part of this release, and the site gets
the editions of 0.11.0 and of this one.

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
- **`PARSER_VERSION` is 21** (0.11.0: 20); a record of a file with several
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

- **A label heading with a colon before a statement's last words no longer
  cuts the statement short.** "P101 Ist ärztlicher Rat erforderlich,
  Verpackung oder" over "Sicherheitshinweise: Kennzeichnungsetikett
  bereithalten." is read as the whole P101, as SDB-184 does for a heading on
  a line of its own (SDB-200). On a set of about 14,500 sheets one reading
  changes and loses `wording-deviates`.
- **A date that can only be read month first is read so.** "08/31/2020" is
  31 August 2020; a date that can be read either way is still read day
  first. "Ausgabedatum/" with the rest of its label below the date labels
  the issue date (SDB-201). On a set of about 14,500 sheets 3 sheets that
  were undated get their issue date.
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
