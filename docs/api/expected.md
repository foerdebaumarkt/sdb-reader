# What the regulation expects

A reading holds what the label prints, and nothing else: the signal word it
prints, the pictograms it names or shows. What the CLP Regulation expects of
the label is not in it. `clp_expected(label)` gives that apart, from the
label's codes, together with where the reading differs from it. What a
difference means for your program is yours to decide: the function reports,
it does not correct.

```python
from sdb_reader import clp_expected

expected = clp_expected(sheet.hazard_statements)
assert expected.signal_word == "Achtung"
assert expected.pictograms == ["GHS07"]
assert expected.pictograms_missing == ["GHS07"]
assert not expected.signal_word_missing
```

The example sheet prints "Achtung" and no pictogram. Its H315 calls for
"Achtung" and for GHS07, so the pictogram is missing from the reading.

| Field | What it holds |
| --- | --- |
| `signal_word` | `Gefahr`, `Achtung` or None: the word Annex I gives the H codes and the EUH codes of the new hazard classes (EUH380, EUH381, EUH430, EUH431, EUH440, EUH441, EUH450, EUH451); `Gefahr` wins over `Achtung` |
| `pictograms` | the pictograms the H codes call for, with the precedence of Article 26 (H315 beside H318 gives GHS05 only); never GHS04, and no GHS05 where H290 is its only reason |
| `signal_word_missing` | the codes call for a signal word, and the reading has none |
| `signal_word_differs` | the reading has a signal word, and it is not the one the codes call for |
| `pictograms_missing` | called for, and not in the reading |
| `pictograms_not_expected` | in the reading, and no H code calls for them |
| `pictograms_left_out` | in the reading and called for, but Article 26 leaves them out beside another pictogram the reading has |

The signal word follows from the codes and never from the pictograms. A
label without codes expects neither. What depends on the package, which a
sheet does not show, is not claimed: GHS04 is never expected, because
Article 33 CLP lets the transport label of a gas cylinder stand in for it,
and GHS05 is not expected where H290 is its only reason (no H314, no
H318), because Annex I 1.3.6 CLP makes it optional on a package for
consumers. A label that prints either is right as well. GHS08 on an
aerosol stays in `pictograms_not_expected` where no H code calls for it,
but is no finding: Annex I 1.3.3 CLP lets an aerosol leave out the
aspiration hazard, and GHS08 may stand for it.

The size of the package matters too. Annex I 1.5.2.1.3 lets a package of at
most 125 ml leave out every element of "corrosive to metals": where the
label may be such a package's, because the sheet prints no small package's
label beside it, H290 calls for no signal word. `clp_expected(label,
small_package=True)` judges a small package's label (`FurtherLabel.label`):
H290 then calls for nothing, and on an aerosol neither do H222, H223 and
H229, for which 1.5.2.1.1 refers to the aerosol directive. A signal word the
codes call for without these exceptions does not count as differing.

## Before you call something missing

The comparison is plain: it does not know why the reading lacks something.
Three fields of the reading tell you more, and the findings use them:

- `drawing_read`: the label was looked at as drawn and every red diamond in
  it was named. Where it is false (a scanned sheet, a label without the
  heading "Kennzeichnungselemente", a diamond nobody could name), a pictogram
  missing from the reading may still be on the page.
- `states_no_signal_word` and `states_no_pictograms`: the label says it has
  none ("Signalwort entfällt", "Gefahrenpiktogramme: keine"). That is the
  sheet's answer, even where the codes call for one.

```python
from sdb_reader import HazardStatements

stated = HazardStatements(hazard_codes=["H319"], states_no_signal_word=True)
assert clp_expected(stated).signal_word_missing
assert stated.states_no_signal_word
```

## Filling a gap

A shop that shows a signal word for every labelled product can take the
expected one where the sheet prints none, and say that it did:

```python
def signal_word_to_show(label: HazardStatements) -> tuple[str | None, bool]:
    """The word to show, and whether it comes from the codes."""
    if label.signal_word is not None or label.states_no_signal_word:
        return label.signal_word, False
    return clp_expected(label).signal_word, True


assert signal_word_to_show(sheet.hazard_statements) == ("Achtung", False)
assert signal_word_to_show(HazardStatements(hazard_codes=["H225"])) == ("Gefahr", True)
```

## Checking a label

A program that checks labels reads the differences. The findings
(`pictogram-not-found`, `pictogram-not-expected`, `pictogram-precedence`,
`signal-word-not-found`; [Judging a sheet](judging.md)) are one such check,
with the exceptions the library applies: nothing where the label states it
has none, no missing pictogram unless the drawing was read, and nothing
for an article or a label under the old law. Like the expectation, a
finding comes only where the library is sure the sheet deviates.

```python
label = HazardStatements(
    hazard_codes=["H315", "H318"], pictograms=["GHS05", "GHS07"], drawing_read=True
)
expected = clp_expected(label)
assert expected.pictograms == ["GHS05"]
assert expected.pictograms_left_out == ["GHS07"]
```

What `clp_expected` returns is part of the package's interface; an
expectation that changes with the regulation is named in the changelog
([What is promised](stability.md)).
