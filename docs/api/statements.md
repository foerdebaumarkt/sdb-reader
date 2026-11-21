# Statements and pictograms

## The label's statements with both wordings

`label_statements(hazards)` lists every H, P and EUH statement of a label as
a `StatementWording` with `code`, `sheet` (the wording the sheet prints) and
`regulation` (the wording of the CLP Regulation).

```python
from sdb_reader import canonical_text, label_statements

statements = label_statements(sheet.hazard_statements)

assert [(s.code, s.sheet) for s in statements] == [
    ("H315", "Verursacht Hautreizungen."),
    ("P102", "Darf nicht in die Hände von Kindern gelangen."),
]
assert statements[0].regulation == canonical_text("H315")
```

`regulation` is None where the regulation has no single wording: a statement
with a gap for the supplier to fill, or a list to choose from. `sheet` is
None for a code the sheet prints without a wording.

`code_source` says whether the label prints the code (`"printed"`) or only
the sentence, to which the parser assigned the code (`"from_wording"`); a
combined code is assigned when each of its parts is. The assigned codes also
stand in `HazardStatements.codes_from_wording`; the code lists hold both kinds.

`as_printed(text, codes_from_wording)` takes the assigned codes off the lines
of a statement text, so that it reads as the sheet prints it:

```python
from sdb_reader import as_printed

text = "P280: Schutzhandschuhe tragen.\nP501 Inhalt/Behälter … entsorgen"
assert as_printed(text, ["P501"]) == (
    "P280: Schutzhandschuhe tragen.\nInhalt/Behälter … entsorgen"
)
```

`canonical_text(code)` gives the regulation's German wording for one code:

```python
assert canonical_text("H315") == "Verursacht Hautreizungen."
assert canonical_text("P280") is None  # "Schutzhandschuhe/Schutzkleidung/… tragen"
```

## Statement texts for display

A label's statement texts are kept as the sheet prints them. Three functions
bring such a text into one form, one statement per line. They are meant to be
run in this order.

| Function | Does |
| --- | --- |
| `normalize_statements(text, prefixes)` | puts each statement on its own line with a colon after its code; *prefixes* names the kinds of code the text holds, such as `("H", "EUH")` or `("P",)` |
| `render_statements(text)` | replaces each line's wording with the regulation's where it has exactly one; returns the text and how many lines it replaced |
| `tidy_statements(text)` | drops a statement that stands twice and a bare code whose wording stands beside it |

```python
from sdb_reader import normalize_statements, render_statements, tidy_statements

printed = (
    "H315 Reizt die Haut. H319 Verursacht schwere Augenreizung. H315 Reizt die Haut."
)

lines = normalize_statements(printed, ("H", "EUH"))
assert lines.splitlines()[0] == "H315: Reizt die Haut."

rendered, replaced = render_statements(lines)
assert replaced == 2

assert tidy_statements(rendered) == (
    "H315: Verursacht Hautreizungen.\nH319: Verursacht schwere Augenreizung."
)
```

EUH statements keep the sheet's wording, since many of them name a substance.

## Pictograms from H codes

`pictograms_for(h_codes)` gives the pictograms that follow from H codes under
the CLP Regulation. A pictogram that Article 26 lets another one replace is
left out; `apply_precedence=False` keeps it. A joined code such as
`H300+H310` counts as its parts.

```python
from sdb_reader import pictograms_for

assert sorted(pictograms_for({"H225", "H302"})) == ["GHS02", "GHS07"]
assert sorted(pictograms_for({"H300", "H302"})) == ["GHS06"]
assert sorted(pictograms_for(set(sheet.hazard_statements.hazard_codes))) == ["GHS07"]
```

The parser does this itself where a label names no pictogram, and says so
with the message `pictograms-derived`.
