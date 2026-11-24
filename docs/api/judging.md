# Judging a sheet

A reading says what the sheet prints. Three functions say what follows from
it for the sheet as a document.

## Findings

`sheet_findings(sheet, parser_warnings)` lists what is wrong with a sheet as
a document, as messages. It takes the sheet and the parser's warnings, which
carry what the parser noticed.

```python
from sdb_reader import Message, sheet_findings

findings = sheet_findings(sheet, reading.parser_result.warnings)
assert findings == [Message("pictogram-not-found", {"pictogram": "GHS07"})]
```

The example sheet is from 2024. It prints no pictogram, though its H315
calls for GHS07; that is all there is to report. The same sheet revised in
2019 would be reported for its age as well:

```python
import dataclasses
from datetime import date

older = dataclasses.replace(sheet, revision_date=date(2019, 5, 2))
findings = sheet_findings(older, reading.parser_result.warnings)

assert Message("predates-annex-ii", {"revised": "2019-05-02"}) in findings
```

A date in the future cannot be right and is no date, but the library reads
no clock. Pass the day as `today`, and a revision or issue date after it is
reported (`revised-in-future`, `issued-in-future`) and no longer counts for
the sheet's age: the sheet is judged by its other date where that is
possible, else like a sheet without a date. The `SafetyDataSheet` keeps the
date as read; `reading_to_dict` takes the same argument and then gives no
date in its place (`null`). For a file of several sheets each date is the
newest one of its sheets names that is not in the future. Without `today` no
date is questioned. The command `read` passes the machine's date.

```python
misprinted = dataclasses.replace(sheet, revision_date=date(2028, 11, 28))
codes = [
    finding.code
    for finding in sheet_findings(
        misprinted, reading.parser_result.warnings, today=date(2026, 11, 18)
    )
]

assert codes[0] == "revised-in-future"
assert "revised-in-future" not in [
    finding.code
    for finding in sheet_findings(misprinted, reading.parser_result.warnings)
]
```

| Code | Values | The sheet |
| --- | --- | --- |
| `predates-annex-ii` | `revised` | was revised before 2021-01-01 and cannot meet Annex II of REACH as amended in 2020 |
| `revised-in-future` | `revised`, `today` | names a revision date after the day given as `today`; that date is no date |
| `issued-in-future` | `issued`, `today` | names an issue date after the day given as `today`; that date is no date |
| `old-format` | `revised` | was revised since, needs to be a sheet by law, and still lacks what the 2020 version added |
| `undated` | – | carries no revision or issue date that can be read |
| `old-classification` | – | classifies under the directives before CLP and carries no CLP label |
| `classification-undetermined` | – | says on its label that the classification was not determined |
| `classification-not-stated` | – | states no classification in section 2 and carries an empty label |
| `classification-contradicts-label` | – | says "not classified" in section 2 while the label carries an H statement, a signal word or a pictogram |
| `euh-outside-label` | `statement`, `sentence` | prints an EUH statement only outside its label |
| `different-products` | `products` | is a file of several sheets whose product names are not one product's; only with `parts` |
| `country-editions-differ` | `fields` | is a file holding one product's sheets for different countries that differ in these fields; only with `parts` |
| `wording-deviates` | `statement`, `sheet`, `regulation` | words a statement differently from the regulation |
| `signal-word-not-found` | `expected` | prints no signal word its codes call for; not where the label states it has none |
| `pictogram-not-found` | `pictogram` | lacks a pictogram its H statements call for; only where the label was looked at as drawn (`drawing_read`), not where it states it has none |
| `pictogram-not-expected` | `pictogram` | names or shows a pictogram none of its H statements calls for; not GHS08 on an aerosol, where it may stand for the aspiration hazard |
| `pictogram-precedence` | `pictogram`, `beside` | shows GHS07 beside a pictogram that Article 26 CLP lets it give way to |
| `hazard-statement-not-classified` | `statement`, `classified` | prints a hazard statement the classification in 2.1 does not name; either side may be wrong |
| `small-package-hazard-statement-not-in-label` | `statement` | prints a small package's label that lacks a hazard statement of 2.1 which CLP Annex I 1.5.2.1 does not let it leave out |
| `small-package-signal-word-not-found` | `expected` | prints a small package's label with a signal word field and none of the word the product's codes call for |
| `signal-word-conflicts` | `printed`, `expected` | prints a signal word that surely conflicts with the product's codes; either side may be wrong |
| `small-package-signal-word-conflicts` | `printed`, `expected` | the same for a small package's label |
| `small-package-pictogram-not-found` | `pictogram` | prints a small package's label that lacks a pictogram the product's H statements call for (2.1, the label and its own); only where it was looked at as drawn and speaks of pictograms |

Where a sheet prints no small package's label, its label may be one: a
statement CLP Annex I 1.5.2.1 lets such a package leave out (H315, H319,
H410, H411 and others) is then not reported as missing, nor a label without
hazard or precautionary statements where every hazard is of that kind.

The checks behind two of them are exported for use on their own:
`predates_annex_ii(revised)` and `contradicts_label(sheet)`.
`predates_clp(revised)` says whether a
sheet predates 2015-06-01, from when mixtures had to be classified under
CLP; it is not among the findings. `euh_outside_label(parser_warnings)`
gives the parser's messages about EUH statements outside the label.

```python
from sdb_reader import contradicts_label, predates_annex_ii, predates_clp

assert predates_annex_ii(date(2020, 12, 31)) is True
assert predates_annex_ii(date(2021, 1, 1)) is False
assert predates_clp(date(2015, 5, 31)) is True
assert contradicts_label(sheet) is False
```

A finding is an observation. What your program does about it is its own
decision. The findings on signal word and pictograms come from
`clp_expected`, which gives the same comparison as data
([What the regulation expects](expected.md)).

## What the label states

`classification(hazard_codes, signal_word, parser_warnings)` says what the
label states, as a `Classification`:

| Member | Value | The label |
| --- | --- | --- |
| `CLASSIFIED` | `classified` | carries an H statement or a signal word |
| `NOT_CLASSIFIED` | `not-classified` | carries neither |
| `UNDETERMINED` | `undetermined` | says that the classification was not determined |
| `OLD_SYSTEM` | `classified-old-system` | is missing because section 2 classifies under the directives before CLP |

```python
from sdb_reader import Classification, classification

label = sheet.hazard_statements
stated = classification(
    label.hazard_codes, label.signal_word, reading.parser_result.warnings
)

assert stated is Classification.CLASSIFIED
```

This is the label's answer. What section 2 itself says about the
classification is `sheet.stated_classification`
([A reading and its parts](reading.md#the-sheet)).

## Whether the product needs a sheet

`sheet_duty(sheet)` says whether a
sheet is one its product needs by law (`SheetDuty.REQUIRED`) or not
(`SheetDuty.NOT_REQUIRED`): section 2 classifies the product, or
the label carries an H or EUH statement, a signal word or a pictogram, or
says that a safety data sheet is to be had on request (also in the old
directive's words, which a label by the old directives prints without a
code). P statements alone do not count.

It weighs the sheet's own word as well. `sheet.stated_voluntary` says the
sheet calls itself issued voluntarily or says that none is prescribed for
its product. `sheet.stated_article` says it calls the product an article,
beside that
sentence or by saying that as an article it is not subject to labelling. An
article needs no sheet, whatever its label prints and whether or not the
sheet calls itself voluntary, and neither does a mixture that is not
classified and whose sheet calls itself voluntary. A classified mixture that is
not called an article still needs one: the regulation spares the supplier
the sheet only towards the general public, and a distributor or downstream
user who asks is owed it. EUH210 or the request sentence at the label
outweigh the word in every case.

```python
from sdb_reader import HazardStatements, SheetDuty, StatedClassification, sheet_duty

assert sheet_duty(sheet) is SheetDuty.REQUIRED

# The same label on a sheet that calls its product an article.
as_article = dataclasses.replace(sheet, stated_article=True)
assert sheet_duty(as_article) is SheetDuty.NOT_REQUIRED

# Only P statements, and nothing said in section 2.
advice = dataclasses.replace(
    sheet,
    hazard_statements=HazardStatements(precautionary_codes=["P102"]),
    stated_classification=StatedClassification.NOT_STATED,
)
assert sheet_duty(advice) is SheetDuty.NOT_REQUIRED
```

Where the reading holds no label (`sheet.label_withheld`), the answer is
`SheetDuty.NOT_CHECKED`: not checked under the rules in force. That is so
for every sheet of the rules before June 2017, whose classification in
section 2 does not count either, and for an incomplete label unless section
2 classifies the product, since the label might carry EUH210. What to do
then is yours to decide.

```python
old = dataclasses.replace(sheet, label_withheld="before-2017-06")
assert sheet_duty(old) is SheetDuty.NOT_CHECKED
```

`reading_to_dict` puts the answer into the record as `sheet.sheet_duty`.

### Judging a sheet you stored

A sheet kept as JSON, the `sheet` part of a record, is read back with
`sheet_from_dict` and judged like any other:

```python
from sdb_reader import sheet_from_dict, sheet_to_dict

stored = sheet_to_dict(sheet, reading.extraction)
kept = sheet_from_dict(stored)

assert kept == sheet
assert sheet_duty(kept) == stored["sheet_duty"]
```

It reads what this version of the library writes. A record that lacks a key
or holds a value of another kind was stored by another version; it is
refused with `ValueError` and not guessed at. Compare `PARSER_VERSION` with
the one you stored ([Keeping texts](stored-texts.md)), and make an outdated
reading again from its text.

Not read for this is section 2.3 (PBT and vPvB substances, the candidate
list), which can also make a sheet obligatory.
