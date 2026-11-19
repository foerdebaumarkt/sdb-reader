# Blätter lesen

## Eine Datei, mehrere Dateien, ein Ordner

```bash
sdb-reader read sheet.pdf
sdb-reader read sheet.pdf other.pdf
sdb-reader read folder/ > result.json
```

`read` nimmt eine oder mehrere PDF-Dateien; ein Ordner steht für jedes PDF
in ihm und seinen Unterordnern. Es gibt ein Ergebnis als JSON
aus, mit einem Datensatz je Datei in der angegebenen Reihenfolge. JSON ist
ein Textformat, das Programme lesen können; ein Texteditor oder ein Browser
zeigt es ebenfalls an. Mit `>` geht das Ergebnis in eine Datei statt auf den
Bildschirm.

Jede Datei wird allein nach ihrem Inhalt beurteilt. Ihr Name spielt keine
Rolle.

Wer das Ergebnis selbst lesen will, bekommt es mit [`show`](anzeigen.md)
als Bericht statt als JSON.

## Optionen

| Option | Wirkung |
| --- | --- |
| `--max-pages N` | nur die ersten N Seiten jeder Datei lesen; ohne die Option alle Seiten |
| `--include-raw-text` | den aus jedem PDF gelesenen Text ins Ergebnis aufnehmen |
| `--indent N` | Leerzeichen der Einrückung im JSON, ohne Angabe 2; `0` schreibt das ganze Ergebnis in eine Zeile |
| `--output DATEI`, `--resume`, `--jobs N`, `--exclude-from DATEI` | für einen Lauf über viele Dateien, siehe [Einen ganzen Bestand lesen](bestand.md) |
| `--lang de` oder `--lang en` | Sprache der Meldungen; ohne Angabe Deutsch |
| `--messages DATEI` | die Sätze der Meldungen aus einer eigenen Datei nehmen |

Die beiden letzten sind unter
[Die Ausgabe verstehen](ausgabe.md#meldungen) erklärt.

## Was zurückkommt

Für ein Blatt sieht der Datensatz so aus, gekürzt:

```json
[
  {
    "file": {"path": "/data/reiniger.pdf", "filename": "reiniger.pdf", "size_bytes": 1385},
    "verification": {"kind": "safety-data-sheet"},
    "extraction": {"extractor": "pymupdf", "pages_sampled": 1},
    "sheet": {
      "product_identifier": "Musterreiniger",
      "revision_date": "2019-05-02",
      "version": "3.1",
      "stated_classification": "classified",
      "stated_voluntary": false,
      "stated_article": false,
      "sheet_required": true,
      "hazard_statements": {
        "signal_word": "Achtung",
        "pictograms": ["GHS07"],
        "hazard_codes": ["H315"],
        "precautionary_codes": ["P102"]
      },
      "contact_info": {"supplier_name": "Muster GmbH"}
    },
    "statements": [
      {
        "code": "P102",
        "sheet": "Darf nicht in Kinderhände gelangen.",
        "regulation": "Darf nicht in die Hände von Kindern gelangen."
      }
    ],
    "findings": [
      {
        "code": "predates-annex-ii",
        "params": {"revised": "2019-05-02"},
        "message": "Überarbeitet am 2019-05-02, vor dem 01.01.2021: Das Blatt kann Anhang II der REACH-Verordnung in der Fassung der Verordnung (EU) 2020/878 nicht erfüllen."
      }
    ]
  }
]
```

[Die Ausgabe verstehen](ausgabe.md) erklärt jeden Teil.

## Exit-Codes

Ein Programm, das endet, hinterlässt eine Zahl, seinen Exit-Code. Ein Skript
kann ihn prüfen; auf der Befehlszeile zeigt `echo $?` den letzten.

| Exit-Code | Bedeutung |
| --- | --- |
| 0 | jede Datei wurde gelesen |
| 1 | mindestens eine Datei ließ sich nicht lesen; sie und die übrigen stehen im Ergebnis, und jeder Fehlschlag wird auf der Fehlerausgabe genannt |
| 2 | ein Pfad ist weder Datei noch Ordner, ein Ordner enthält kein PDF, eine Option ist falsch, oder für die gewünschte Sprache gibt es keinen Katalog; gelesen wurde nichts |
| 130 | der Lauf wurde mit Strg-C abgebrochen |

Eine Datei, die kein Sicherheitsdatenblatt ist, ist kein Fehlschlag. Sie
bekommt einen Datensatz, der sagt, was sie ist, und der Exit-Code bleibt 0.

Eine Datei, aus der sich kein Text lesen lässt, etwa ein leerer Scan oder
eine Datei, die kein PDF ist, ist ein Fehlschlag. Sie steht trotzdem im
Ergebnis, mit dem Grund:

```text
[sdb-reader] FEHLER: leer.pdf: Aus dem PDF ließ sich kein Text lesen (1 Seite angesehen, gelesen mit pymupdf+ocr).
```

## Ergebnis und Fehlerausgabe

Das Ergebnis geht auf die Standardausgabe, und sonst nichts. Zeilen über
Fehlschläge und Hinweise, die das Programm beim Lesen schreibt, gehen auf
die Fehlerausgabe. `> result.json` ergibt deshalb immer eine saubere
Ergebnisdatei, und die Fehlschläge bleiben auf dem Bildschirm.
