# What it handles

A safety data sheet looks like a form: sixteen numbered sections, a label in
section 2.2. In practice every supplier's software lays it out differently,
the law behind it has changed several times since 2010, and a label
may print its pictograms as codes, as pictures, or both. This page lists
what the reader deals with, each point as *the sheet does this, the reader
does that*. The IDs in brackets name the rules behind a point; the rules are
in German, in [specs/](../specs/README.md). How a file passes through the
library step by step is told in [How it works](how-it-works.md).
The short list: [Features at a glance](features.md).
Deutsch: [Was es abdeckt](was-es-abdeckt.md).

## The file

- **Not every file called a safety data sheet is one.** The reader sorts
  each file into one of four kinds: a German safety data sheet, a safety
  information (a document laid out like a sheet that does not call itself
  one), a safety data sheet in another language, or another document. A
  title with a typo still counts; a sentence that only mentions a safety
  data sheet is no title (SDB-59, SDB-66, SDB-68, SDB-105, SDB-140,
  SDB-141).
- **Several sheets in one file.** Country editions, a kit with one sheet
  per component: the reader finds each sheet (a list of changes is none),
  reads each on its own and the file as a whole, says whether the sheets
  are of the same product and which is the oldest, and skips a cover page (SDB-2, SDB-118, SDB-138, SDB-139, SDW-36, SDW-45).
- **Scans.** A file without a text layer is read by text recognition, and
  so is a single scanned page in a file whose other pages have text
  (SDB-46, SDB-95, SDB-116).
- **A text layer in odd order.** The reader puts the words back in the
  order they are printed, keeps tables and columns apart, joins words split
  at the end of a line and words a file draws in pieces (SDB-32, SDB-42 to
  SDB-45, SDB-54, SDB-99).
- **Headings in many forms.** "ABSCHNITT 2", "2.", "2:", with a mark for a
  changed section, and the order of sections from before REACH, when
  composition and hazards were the other way round (SDB-1, SDB-58, SDB-89,
  SDB-152, SDB-175).
- **A file inside the file.** Some PDFs carry the sheet's data as an
  eSDScom XML file. The reader reads it and puts it beside its own reading
  (SDW-11).

## Old rules and new

The law changed twice under the sheets. Until 2015 mixtures were classified
under Directives 67/548/EEC and 1999/45/EC, with R and S phrases and orange
hazard symbols; since then under the CLP Regulation, with H and P statements
and red-framed pictograms. The format of the sheet changed with Regulation
(EU) 2015/830, whose transition ended on 31 May 2017, and again with
2020/878.

- **Three kinds of sheet.** A sheet of the rules before June 2017 is read
  without its label and gets only the findings on its age. A sheet from June
  2017 on that is not yet in the format of 2020/878 is read in full and gets
  every finding, beside the finding that it is due for renewal. A sheet
  under 2020/878 is read in full (SDB-216, SDW-7, SDW-9, SDW-49).
- **Two classifications on one sheet.** A sheet of the transition may call
  the product "not subject to labelling" under the old directives and
  classify it under CLP. For a sheet of the old rules the reader therefore
  says that whether its product needs a sheet is *not checked under the
  rules in force* (SDB-218).
- **Old phrases give no codes.** R and S phrases are not turned into
  H and P statements, and the old sentence "Sicherheitsdatenblatt auf
  Anfrage für berufsmäßige Verwender erhältlich" is not EUH210 (SDB-73,
  SDB-120, SDB-123).
- **The orange symbols of the old directives are no pictograms** and are
  deliberately not taken for any (SDB-207).

## The label

- **Where it begins and ends.** "Kennzeichnungselemente", "Kennzeichnung
  nach GHS", "Etiketteninhalt", "GHS-Kennzeichnung" all begin a label; it
  ends at section 2.3 unless label elements follow there. A page's head and
  foot are no part of it (SDB-4, SDB-156, SDB-202, SDB-205, SDB-209).
- **More than one label.** A label for packages of at most 125 ml, a block
  under the Biocidal Products or the Detergents Regulation: each is kept
  apart, as printed, with what it leaves out (SDB-188, SDB-189, SDB-190).
- **Conditions.** "Obige Kennzeichnung gilt bei Abgabe an privaten
  Endverbraucher" and conditions printed for single statements are kept with
  the label, not merged into it (SDB-191, SDB-192).
- **Statements printed only as sentences.** Where the label prints a
  sentence without its code, the reader names the code from the
  regulation's wording and says that it was assigned, not printed (SDB-6,
  SDB-28, SDB-163, SDB-174, SDW-43).
- **The forms codes come in.** Sentences with a gap ("Enthält … Kann
  allergische Reaktionen hervorrufen."), combined statements
  ("P305+P351+P338"), lists of codes without text, "H 315" with a space,
  H360 and H361 with the letters of their effect, a code printed inside its
  own sentence (SDB-30, SDB-52, SDB-64, SDB-121, SDB-125, SDB-155,
  SDB-164).
- **The sheet's wording beside the regulation's.** For every statement the
  reading gives both and says where they differ (SDB-18, SDW-5, SDW-50).
- **What is not the label.** A code in a classification entry ("Aquatic
  Chronic 1, H410"), a sentence that describes an effect in running text,
  the sentence about an article treated with a biocide: none of them is a
  statement of the label (SDB-5, SDB-41, SDB-196, SDB-219).

## Pictograms

- **Code, picture, or both.** A label names a pictogram as "GHS07", shows
  it as a picture, or does both; the reading says which for each
  (SDB-179, SDB-211).
- **Pictures read from the PDF.** A stage of its own finds the diamonds on
  the page and compares each with the nine pictograms of the regulation
  (BIB-24).
- **In colour, black or grey.** REACH allows a black-and-white pictogram on
  the sheet; the reader finds red, black and grey frames (SDB-212).
- **Drawn in pieces.** Some files draw a pictogram from thin strips;
  pictograms that touch are cut apart (SDB-208).
- **On scanned pages,** where the label is found by the positions of the
  words text recognition reads (SDB-204).
- **Small or unusual drawings.** A diamond named by none at first is looked
  at again in finer detail; the flame (GHS02) and the flame over circle
  (GHS03) are told apart by the ring; a pictogram drawn otherwise but
  clearly most like one is named (SDB-206, SDB-213, SDB-215).
- **Codes misread by text recognition,** such as "GHS007" or "GHS 05"
  (SDB-203).
- **Pictograms in section 2.1** belong to the classification; they count
  only where no label is found (SDB-202).

## Product, supplier, classification and dates

- **The classification** is stated in many wordings, as a hazard class or a
  sentence that the product is not classified; a clause of a condition ("…
  even if they were classified as hazardous") states none (SDB-75, SDB-80,
  SDB-81, SDB-107, SDB-214).
- **The product name** comes from section 1.1, not an article number, a
  formulation code or a reference elsewhere; failing that, from the sheet's
  head (SDB-131, SDB-148 to SDB-150, SDB-153, SDB-158).
- **The supplier** is named under many labels; where a block names several
  firms, the German one counts. The emergency number is told apart from the
  supplier's phone, and a poison centre's number is never the supplier's
  (SDB-49, SDB-50, SDB-55, SDB-117, SDB-132 to SDB-136).
- **Dates** come with the month as a word, the year first, the month first,
  a weekday, a word broken over a line; a date in the future is no date; a
  file with several sheets has the newest date of them (SDB-57, SDB-90,
  SDB-128, SDB-129, SDB-137, SDB-161, SDB-182, SDB-201).
- **The version** is the number the file names most often, without those it
  calls replaced; the countries the sheet is issued for are DE, AT and CH
  (SDB-20, SDB-69).
- **The current sheet** among several of one product is chosen by date,
  country and version (BIB-6 to BIB-9).

## Findings

Where a sheet falls short of the CLP Regulation or REACH, the reader says so
as a finding beside the reading: a classified product without a label, a
statement on the label the classification does not name or the other way
round, a signal word that contradicts the codes, a pictogram that should
give way to another, a statement worded otherwise than the regulation, a
classification that contradicts the label, a sheet due for renewal, sheets
of different products in one file (SDB-79, SDB-170 to SDB-173, SDB-181,
SDB-197, SDB-199, SDW-7, SDW-9, SDW-36, SDW-42).

- **Only where it is sure.** Where the answer depends on what the sheet does
  not say, such as the size of the package or who buys the product, there is
  no finding (SDB-169, SDB-183, SDB-193, SDB-194).
- **Checked one by one.** The findings that a label lacks something, or
  carries what it should not, are checked case by case against a stock of
  about 14,850 sheets before a release. Many cases turned out to be
  misreadings and were put right in the reader; a finding also checks the
  reading.

## Safe by default

- **An incomplete label is withheld.** Where a label surely lacks what it
  must show, the reading gives it out only on request, so that no program
  shows a hazardous product without its warnings by mistake (SDB-217,
  BIB-26).
- **Three answers to "does the product need a sheet?"**: yes, no, or not
  checked under the rules in force (SDB-76, SDB-142, SDB-154, SDB-218).
- **The same file gives the same result.** No language model, and no clock:
  what depends on today's date gets it from the caller (BIB-19).

What the reader does not do yet is listed under "Limits" in the
[README](https://github.com/foerdebaumarkt/sdb-reader/blob/main/README.md#limits)
and under "Offene Fragen" in the specs.
