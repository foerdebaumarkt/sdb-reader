# Understanding the output

Each file gets one record. This page goes through its parts in the order
they appear.

## What the file is

`verification.kind` says what the file is. There are four kinds:

| `kind` | The file is | What the record holds |
| --- | --- | --- |
| `safety-data-sheet` | a German safety data sheet | `sheet`, `statements`, `parser`, `findings`, `sheet_count`, `cover_page`, `display_term`; `parts` where the file holds [several sheets](#several-sheets-in-one-file) |
| `safety-information` | laid out like a safety data sheet, without calling itself one | the verdict only |
| `safety-data-sheet-other-language` | a safety data sheet in another language | the verdict and the finding `not-german` |
| `document` | anything else, or a file no text could be read from | the verdict; `errors` says why if nothing could be read |

Only the first kind is read further, and only its record has `sheet`,
`statements`, `parser` and `sheet_count`. Every record has the lists `warnings`, `errors` and
`findings`; a list with nothing to say is empty, not missing. `verification.errors` says why a
file is no German safety data sheet, and
`verification.warnings` what was noticed on the way.

A safety information (Sicherheitsinformation) is what suppliers issue for
products that need no safety data sheet. It has the sixteen sections but not
the title. A leaflet on handling an article that titles itself
"Sicherheitsdatenblatt zum sicheren Umgang mit …" and does not name
Regulation (EC) No 1907/2006, such as a battery maker's, is one too: what it
prints as classification belongs to its ingredients, not to the product's
label.

## How the text was read

`extraction` says how the text was won from the PDF:

| Field | Meaning |
| --- | --- |
| `stage` | the reading stage the text comes from: its version and that of the PDF library; two runs of different stages may differ because the text differs, see [Comparing two runs](comparing-runs.md) |
| `extractor` | `pymupdf` for a PDF that carries its text; `pymupdf+ocr` where text recognition read the pages |
| `pages_sampled` | how many pages were read |
| `character_count` | how many characters the text has |
| `tesseract` | the version of the text recognition program that read the text; only where it read pages |
| `warnings` | what was noticed, as [messages](#messages) |

Text read by text recognition is less reliable than text the PDF carries.
Check such a sheet more carefully.

## The sheet

`sheet` holds what a German safety data sheet says:

| Field | Meaning |
| --- | --- |
| `product_identifier` | the trade name from section 1.1 |
| `revision_date`, `issue_date` | date of revision and date of issue, as year-month-day; the newest where the sheet names several |
| `version` | the sheet's own version number |
| `countries` | the countries the sheet is issued for, of `DE`, `AT`, `CH`; empty where it names none |
| `stated_classification` | what section 2 says about the classification, see below |
| `stated_voluntary`, `stated_article` | whether the sheet calls itself voluntary or not prescribed, and whether it calls the product an article there, see below |
| `sheet_required` | whether the product needs a safety data sheet by law, see below |
| `hazard_statements` | the label of section 2.2, see below |
| `contact_info` | the supplier of section 1.3 with name, address, phone, e-mail and website, and the emergency phone of section 1.4, as printed with what the sheet says about it ("(24 h)", the poison centre's name); `information_email` is the address the sheet names for whoever answers for it: the competent person's ("E-Mail-Adresse der sachkundigen Person"), else an information office's ("Auskunftgebender Bereich"). It is null where no such label stands at an address, it may equal `email`, and it may be the address of a firm that wrote the sheet for the supplier |
| `section_text` | the text of each section that was found |
| `content_hash` | a fingerprint of the text; two files with the same one have the same content |

### The classification

`stated_classification` is what section 2 says:

| Value | Section 2 says |
| --- | --- |
| `classified` | the product is classified as hazardous under the CLP Regulation |
| `classified-old-system` | it is classified under the directives before CLP (R phrases, hazard symbols) |
| `not-classified` | it is not classified |
| `not-stated` | neither |

### Whether the product needs a sheet

`sheet_required` is `true` where section 2 classifies the product, or where
the label carries a hazard statement (H or EUH), a signal word or a
pictogram. Every other sheet was issued voluntarily. Precautionary statements
(P) alone do not count: a supplier may print them on any product.

`stated_voluntary` is `true` where the sheet says of itself that it was
issued voluntarily or that no safety data sheet is prescribed for the
product ("Für dieses Produkt ist gemäß Artikel 31 der REACH-Verordnung kein
Sicherheitsdatenblatt erforderlich.", "Dieses Sicherheitsdatenblatt wurde
freiwillig erstellt", "… für Erzeugnisse nicht vorgeschrieben").
`stated_article` is `true` where it calls the product an article
("Erzeugnis") beside that sentence, or where it says the product is an
article and therefore not subject to labelling ("Dieses Produkt ist ein
Erzeugnis, deshalb ist es … nicht kennzeichnungspflichtig"); such a sheet
need not call itself voluntary. What follows for `sheet_required`:

| The sheet … | `sheet_required` |
| --- | --- |
| calls the product an article | `false`, also where the label prints H statements |
| calls itself voluntary, and the product is not classified (section 2 does not classify it, no H statement) | `false` |
| calls itself voluntary, but the mixture is classified and no article is named | `true`: the sheet is due to a distributor or downstream user who asks for it |
| prints EUH210 or the sentence "auf Anfrage erhältlich" at the label | `true`, in every case |

The label always stands in the reading as the sheet prints it.

### The label

`hazard_statements` is the label (Kennzeichnung) of section 2.2:

| Field | Meaning |
| --- | --- |
| `hazard_codes` | the codes of the hazard statements (H); H360 and H361 with the letters of their effect, as Annex VI of the CLP Regulation sets them (`H360D`, `H361fd`) |
| `precautionary_codes` | the codes of the precautionary statements (P) |
| `supplemental_codes` | the codes of the supplemental statements (EUH) |
| `signal_word` | `Gefahr` or `Achtung` as the label prints it, or nothing |
| `pictograms` | the codes of the pictograms the label prints, `GHS01` to `GHS09`: those its text names and those it shows as pictures |
| `drawing_read` | whether the label was looked at as drawn and every red diamond in it named |
| `states_no_signal_word`, `states_no_pictograms` | whether the label states it has none ("Signalwort entfällt", "Gefahrenpiktogramme: keine") |
| `hazard_text`, `precautionary_text`, `supplemental_text` | the statements as the sheet prints them; a code the sheet does not print stands in front of its sentence |
| `codes_from_wording` | the codes the label does not print: the sheet prints only the sentence, and the parser assigned the code; each also stands in its list above |
| `condition`, `condition_text` | whom the label says it applies to, and the sentence that says it: `consumers` for "Obige Kennzeichnung gilt bei Abgabe an privaten Endverbraucher."; otherwise `null` |
| `statement_conditions` | single statements printed with a condition, by code: `consumers` ("Nur für private Endverbraucher: P101 …"), `not-general-public` (EUH210 for packages not meant for the general public); the codes stand in the lists above as well |
| `further_labels` | the blocks of 2.2 beside the label, see below |

The label holds only what the sheet prints. The signal word is the printed
one. Pictograms are the printed ones: most sheets print them as pictures,
and `read` looks at the label on the page for red diamonds and names each.
Nothing is derived from the codes. Where the label differs from what its
codes call for under the CLP Regulation, the findings say so
(`signal-word-not-found`, `pictogram-not-found`, `pictogram-not-expected`,
`pictogram-precedence`); a label that states it has none gets no finding
that one was not found. Where the label could not be looked at (a scanned
sheet, a label without the heading "Kennzeichnungselemente") or a diamond
stayed unnamed, `parser.warnings` says so (`label-images-not-read`,
`pictograms-not-recognised`) and `drawing_read` is false.

### Blocks beside the label

Some sheets print more than one label in 2.2. `further_labels` holds each
block beside the label, in the sheet's order, and nothing of it stands in
the label above:

| Field | Meaning |
| --- | --- |
| `kind` | `small-package`: the label of a package of at most 125 ml (CLP Annex I 1.5.2.1); `biocides`: a block under Regulation (EU) No 528/2012; `detergents`: a block under Regulation (EC) No 648/2004 |
| `heading` | its heading as printed; for a sentence that says what a small package leaves out ("Reduzierte Kennzeichnung <= 125 ml: H225 und H319 entfallen."), that sentence |
| `text` | its lines as printed, without the heading |
| `omitted_codes` | the codes such a sentence says a small package leaves out |
| `label` | what a small package's label carries, in the same fields as the label above (without `further_labels`); empty for the other kinds |

Which label applies is yours to decide: the label above is the product's,
and a small package's label is the one of a package of at most 125 ml.
Where a sheet prints no small package's label, its label may be one: a
statement such a package may leave out is then not reported as missing.

## The statements

`statements` lists every statement of the label with two wordings:

| Field | Meaning |
| --- | --- |
| `code` | the statement's code, such as `P102` |
| `sheet` | the wording the supplier printed |
| `regulation` | the wording of the CLP Regulation; empty where the regulation has no single one, for a statement with a gap to fill or a list to choose from |
| `code_source` | `printed` where the label prints the code, `from_wording` where it prints only the sentence and the parser assigned the code |

To show the statements as the sheet prints them, leave out the code of a
statement whose `code_source` is `from_wording`.

## What the regulation expects

`clp_expected` stands beside the sheet and is not part of it: what the CLP
Regulation expects of the label, worked out from its codes, and where the
label as read differs. The label itself stays as printed under
`sheet.hazard_statements`. Whether a difference matters is yours to decide:
fill a gap with it, or check a label by it.

| Field | Meaning |
| --- | --- |
| `signal_word` | `Gefahr`, `Achtung` or nothing: the word the H and EUH codes call for; never from the pictograms |
| `pictograms` | the pictograms the H codes call for, with the precedence of Article 26 CLP; never GHS04 (Article 33 CLP), no GHS05 where H290 is its only reason (Annex I 1.3.6 CLP) |
| `signal_word_missing` | the codes call for a signal word, and the label as read has none |
| `signal_word_differs` | the label as read has a signal word other than the one the codes call for |
| `pictograms_missing` | called for, and not in the label as read |
| `pictograms_not_expected` | in the label as read, and no H code calls for them |
| `pictograms_left_out` | in the label as read and called for, but Article 26 leaves them out beside another it has |

Before calling something missing, look at `drawing_read`,
`states_no_signal_word` and `states_no_pictograms` under
`sheet.hazard_statements`: a label that could not be looked at as drawn may
still show a pictogram, and one that states it has none has answered. The
findings take both into account; this block does not. For a file of several
sheets each entry of `parts` carries its own. A record written before has no
such block.

## The findings

`findings` lists what is wrong with the sheet as a document. Each is a
[message](#messages). A sheet that has to be renewed anyway
(`predates-annex-ii`, `old-format`) gets only the findings on its age and
those on a file of several sheets: what else it lacks is for its new edition
to put right.

| `code` | Meaning |
| --- | --- |
| `predates-annex-ii` | revised before 2021, so it cannot follow today's rules for the content of a sheet |
| `old-format` | revised since 2021 but still laid out as before |
| `revised-in-future` | the revision date lies after the day `read` ran; it cannot be right and is no date: `revision_date` is `null`, and the sheet is judged by its issue date if that is possible, else as undated |
| `issued-in-future` | the same for the issue date: `issue_date` is `null` |
| `undated` | no date of revision or issue that can be read |
| `old-classification` | classified under the directives before CLP, without a CLP label |
| `classification-undetermined` | the label says the classification is not determined |
| `classification-not-stated` | section 2 neither names a hazard class nor says the product is not classified, and the label is empty |
| `classification-contradicts-label` | section 2 says not classified, yet the label carries a hazard statement, a signal word or a pictogram |
| `euh-outside-label` | a supplemental statement printed only outside the label |
| `different-products` | the file holds sheets of different products; `products` names them. See [Several sheets in one file](#several-sheets-in-one-file) |
| `country-editions-differ` | the file holds the same product's sheets for different countries, and they differ in the `fields` named |
| `wording-deviates` | a statement worded differently from the regulation |
| `pictogram-not-found` | the H statements call for a pictogram the label does not print; only where `drawing_read` |
| `pictogram-not-expected` | the label prints a pictogram none of its H statements calls for; not GHS08 on an aerosol, where it may stand for the aspiration hazard (Annex I 1.3.3 CLP) |
| `pictogram-precedence` | the label prints GHS07 beside a pictogram Article 26 CLP lets it give way to |
| `hazard-statement-not-classified` | the label prints a hazard statement the classification in 2.1 does not name (`statement`; `classified` lists what 2.1 names); either side may be the wrong one |
| `small-package-hazard-statement-not-in-label` | a small package's label lacks a hazard statement of 2.1 that Annex I 1.5.2.1 CLP does not let it leave out |
| `small-package-signal-word-not-found` | a small package's label names a signal word field, and prints none the product's codes call for |
| `small-package-pictogram-not-found` | a small package's label lacks a pictogram the product's H statements call for (2.1, the label and its own); only where it was looked at as drawn and speaks of pictograms |
| `not-german` | the sheet is in another language |

A finding is an observation about the document. What follows from it, such
as asking the supplier for a newer sheet, is your decision.

## Messages

Whatever the program notes about a file is a message: what it noticed while
reading the text, judging the file and reading the sheet, the reason a file
could not be read, and the findings. Every message has three parts:

```json
{
  "code": "wording-deviates",
  "params": {
    "statement": "P102",
    "sheet": "Darf nicht in Kinderhände gelangen.",
    "regulation": "Darf nicht in die Hände von Kindern gelangen."
  },
  "message": "P102: Das Blatt druckt „Darf nicht in Kinderhände gelangen.“, die Verordnung sagt „Darf nicht in die Hände von Kindern gelangen.“."
}
```

| Part | Meaning |
| --- | --- |
| `code` | what is noted; fixed, and the same in every language |
| `params` | the values the code names |
| `message` | the sentence for a person, in the language you chose |

[All messages](messages.md) lists every code with its sentence.

### Choosing the language

The sentences are German unless you ask for English:

```bash
sdb-reader read --lang en sheet.pdf
SDB_READER_LANG=en sdb-reader read sheet.pdf
```

`SDB_READER_LANG` is an environment variable: a setting the command line
keeps, so that you need not repeat the option. The language is only ever the
one you name. The language of your machine plays no part, so the same file
gives the same result everywhere.

Not translated are the keys, fixed values such as `safety-data-sheet`, and
the statements of the label, which are the sheet's own words.

### Sentences of your own

The sentences come from a catalog, a text file that gives each code its
sentence. To word messages differently, or in another language, write a file
like this and pass it with `--messages`:

```toml
[messages]
"predates-annex-ii" = "Zu alt: überarbeitet am {revised}."
"undated" = "Das Blatt trägt kein Datum."
```

```bash
sdb-reader read --messages my-messages.toml sheet.pdf
```

`{revised}` stands for a value of the message; [All messages](messages.md)
names the values of each code. Your file may hold only the codes you want to
word; the others are said in English. A code or a value the program does not
know is refused before any file is read.

## Several sheets in one file

Some files hold several complete sheets one after another: the two parts of
a two-component adhesive, the products of a combination pack, or the
editions of one sheet for several countries. `sheet_count` says how many the file
holds; for most files it is 1.

For such a file the record gives two readings side by side:

- `sheet`, `statements`, `parser` and `findings` are the file's, with its
  sheets united: every code and pictogram any sheet prints, the stronger
  signal word, the newest date. The message `several-sheets` under
  `parser.warnings` says so.
- `parts` lists each sheet read on its own, in the file's order, as if it
  were a file by itself, each with its own `clp_expected`.
- `oldest_sheet` names the sheet with the oldest date; see
  [The oldest sheet](#the-oldest-sheet).

```json
{
  "sheet_count": 2,
  "sheet": {"revision_date": "2022-07-20", "hazard_statements": {"hazard_codes": ["H315", "H318"], "signal_word": "Gefahr"}},
  "parts": [
    {
      "sheet": {"product_identifier": "Harz", "revision_date": "2022-07-20", "hazard_statements": {"hazard_codes": ["H315"], "signal_word": "Achtung"}},
      "statements": [{"code": "H315", "sheet": "Verursacht Hautreizungen.", "regulation": "Verursacht Hautreizungen."}],
      "warnings": [],
      "findings": []
    },
    {
      "sheet": {"product_identifier": "Härter", "revision_date": "2021-05-03", "hazard_statements": {"hazard_codes": ["H318"], "signal_word": "Gefahr"}},
      "statements": [{"code": "H318", "sheet": "Verursacht schwere Augenschäden.", "regulation": "Verursacht schwere Augenschäden."}],
      "warnings": [],
      "findings": []
    }
  ],
  "oldest_sheet": {"sheet": 2, "date": "2021-05-03", "dated_by": "revision"}
}
```

(Shortened: each `sheet` under `parts` has every field of [The sheet](#the-sheet).)

Which reading is the right one depends on the file, and the program cannot
tell:

- Where the sheets are the parts of one product, the product carries all
  their labels, and the united reading is the product's.
- Where they are different products or editions, the united reading can
  name hazards that no single sheet names, and its date and version belong
  to no single sheet. Take the sheet you need from `parts`.

Each entry holds `sheet` (with the fingerprint `content_hash` of that
sheet's text), `statements` and `warnings`, what was noticed while reading
that sheet, and names its countries (`countries`, empty where none is
recognised) and its product (`product_identifier`). Its `findings` hold
the findings on that sheet's age, judged on its own dates as for a file
that is this sheet: `revised-in-future`, `issued-in-future`, `undated`,
`predates-annex-ii` and `old-format`; the list is empty where there is none. There are no other
findings per sheet: a finding is about the product, and whether one sheet
is the product the program does not know. A later sheet begins at the title "Sicherheitsdatenblatt" above
its section 1, so that the date and version in the header of its first page
count for it. A list of changes that names the sections, and the same sheet
once more in another language, are no further sheets.
[Comparing two runs](comparing-runs.md) compares the file's reading, not
`parts`.

### The oldest sheet

The file's reading carries the newest date the file names, and its
findings on age follow that date. A file whose new resin stands beside a
hardener from 2014 is therefore not reported as old. `oldest_sheet` names
the sheet you would judge such a file by:

| Key | Meaning |
| --- | --- |
| `sheet` | the sheet's number in the file's order, from 1 |
| `date` | its date: the revision date, else the issue date; a date after the day of the run does not count |
| `dated_by` | `revision` or `issue`: which of the two the date is |

Where several sheets share the oldest date, the first counts; where no
sheet carries a date that counts, `oldest_sheet` is `null`. A file of one
sheet has no `oldest_sheet`. Which sheet's date counts for your product is
yours to decide; the file's reading and findings stay as they are.

### What the sheets say about each other

The program compares the sheets of a file and reports what it sees. It
chooses none of them and never changes the united reading: which sheet
counts for your product, only you know.

- `different-products` among the `findings`: the product names of the
  sheets are not one product's. The parts of one product ("… Komponente A"
  and "… Komponente B", "… (Harz)" and "… (Härter)", colours that differ in
  a number at the end) are one product and not reported. Such a file is a
  combination pack or a set, sold as one unit, or a file that belongs to
  something else than the product it is filed under. Where a product name
  could not be read, nothing is reported, because it cannot be told.
- `country-editions-differ`: two sheets carry the same product name and are
  for different countries, and they differ in the fields named (statement
  codes, signal word, pictograms, classification).

### A cover page

Some files begin with a cover page: a page titled "Deckblatt" or
"Sicherheitsdatenblätter für …", a kit's information sheet, a list "Set aus
Sicherheitsdatenblättern bestehend aus:", or a country's additions to the
sheet that follows. A cover page is no
sheet. Nothing is read from it: no date, version, supplier or statement of
the record comes from it, and it is not among `parts`.

| Key | Meaning |
| --- | --- |
| `cover_page` | `true` where a cover page stands in front of the file's sheets |
| `display_term` | the word on the cover page that names a display, as printed (such as "Mix-Display"); `null` where there is no cover page or it names none |

A display is a unit a supplier ships to be set up in a shop, holding
several products. A file with a display's cover page belongs to the
display, not to one of its products.

## Other parts

| Part | Holds |
| --- | --- |
| `file` | path, name and size of the file |
| `parser.warnings` | what was noticed while reading the sheet, such as a label that could not be looked at as drawn; empty where nothing was |
| `warnings` | for a file that is no German sheet or could not be read: that nothing was read further; otherwise empty |
| `errors` | for a file no text could be read from: the reason; otherwise empty |
| `embedded_data` | for a PDF that carries an embedded file: see [The embedded file](embedded-file.md) |
| `raw_text` under `extraction` | with `--include-raw-text`: the text read from the PDF |

The full description of a record, with every key and its type, is a JSON
Schema that ships with the program; programmers find it under
[The JSON schema](../api/schema.md).
