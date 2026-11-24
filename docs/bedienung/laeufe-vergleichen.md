# Zwei Läufe vergleichen

## Wofür

Ein Lauf ist, was `read` oder `ask` für eine Menge von Dateien geschrieben
hat: je Datei ein Datensatz. `diff` stellt zwei Läufe nebeneinander und
sagt Feld für Feld, in wie vielen Dateien sie abweichen, mit Beispielen. Es
liest kein PDF und fragt kein Modell, braucht deshalb Sekunden und lässt
sich beliebig oft wiederholen.

| Läufe | Was der Vergleich zeigt |
| --- | --- |
| `read` und `ask` | wo ein Modell ein Blatt anders liest als das Programm: Stellen, an denen ein Lesefehler stecken kann |
| `read` und `read` | was eine Änderung am Programm an einem Bestand bewirkt, vorher und nachher |
| `ask` und `ask` | wo zwei Modelle oder zwei Läufe eines Modells sich widersprechen |

## Aufruf

```bash
sdb-reader read sheets/ --output read.jsonl --jobs 8
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader diff read.jsonl answers.jsonl
```

Die beiden Läufe heißen in der Reihenfolge der Angabe A und B. Jeder ist
eine Datei mit Datensätzen, wie `read` oder `ask` sie geschrieben hat: JSON
Lines aus `--output` oder die JSON-Liste, die der Befehl sonst ausgibt.
Nennt eine Datei mit JSON Lines ein PDF mehrmals, gilt die letzte Zeile.

| Option | Wirkung |
| --- | --- |
| `--match path` | zwei Datensätze gehören zur selben Datei, wenn ihre Pfade gleich sind; so ist es ohne Angabe |
| `--match name` | zwei Datensätze gehören zur selben Datei, wenn ihre Dateinamen gleich sind, für Läufe über Kopien an verschiedenen Orten; ein Name, den ein Lauf unter mehreren Pfaden enthält, beendet den Befehl |
| `--examples N` | bis zu N Dateien je Feld zeigen; ohne Angabe 3 |
| `--json` | Zahlen und Beispiele als JSON statt als Text ausgeben |
| `--details DATEI` | jede abweichende Datei mit allen ihren Abweichungen und beiden Werten in DATEI schreiben, als JSON Lines; eine vorhandene DATEI wird ersetzt |
| `--count-only-from DATEI` | die Dateien, die DATEI nennt, in einer eigenen Gruppe zählen und keine davon zeigen, siehe unten |
| `--indent N`, `--lang`, `--messages` | wie bei `read` |

Dateien, die nur ein Lauf nennt, werden gezählt und nicht verglichen.

## Was verglichen wird

Zwei Läufe von `read` werden in jedem Feld einer Lesung verglichen. Die
Felder heißen wie in der Ausgabe von `read`:

| `field` | Was verglichen wird |
| --- | --- |
| `kind` | was die Datei ist |
| `stated_classification`, `stated_voluntary`, `stated_article`, `sheet_duty`, `countries` | was Abschnitt 2 zur Einstufung sagt, ob das Blatt sich freiwillig nennt und das Produkt dabei ein Erzeugnis, ob das Produkt ein Blatt braucht, die Länder |
| `signal_word`, `pictograms` | das Signalwort und die Piktogramme |
| `hazard_codes`, `precautionary_codes`, `supplemental_codes` | die Codes der H-, P- und EUH-Sätze |
| `hazard_text`, `precautionary_text`, `supplemental_text` | die Texte der Sätze |
| `revision_date`, `issue_date`, `version`, `product_identifier` | Daten, Version und Produktname |
| `supplier_name`, `supplier_address`, `supplier_phone`, `email`, `supplier_website`, `information_email`, `emergency_phone` | der Lieferant, die E-Mail-Adresse der auskunftgebenden Stelle und die Notrufnummer |
| `findings` | die Codes der Befunde |
| `embedded_differences` | die Felder, in denen die eingebettete Datei vom gelesenen Blatt abweicht |
| `errors` | warum sich eine Datei nicht lesen ließ |

Ist einer der Läufe von `ask`, wird nur verglichen, wonach ein Modell
gefragt wird:

| `field` | Was verglichen wird |
| --- | --- |
| `hazard_codes`, `precautionary_codes`, `supplemental_codes` | die Codes der H-, P- und EUH-Sätze; ein verbundener Code wie P305+P351 zählt als seine Teile |
| `wording` | der Wortlaut eines Satzes, den beide nennen, mit seinem `code`; Groß- und Kleinschreibung, Satzzeichen und Leerraum zählen nicht |
| `supplier_name`, `supplier_email` | Name und E-Mail-Adresse des Lieferanten; Groß- und Kleinschreibung und Leerraum zählen nicht |
| `revision_date` | das Überarbeitungsdatum; ein Modell, das kein Datum nennt, das zählt, weicht von einer Lesung nicht ab, wohl aber von einem anderen Modell, das eines nennt |

Eine Datei, für die einer der beiden Datensätze nichts zu vergleichen hat,
etwa eine Datei, die kein Blatt ist, zählt als nicht vergleichbar.

## Was zurückkommt

```text
A: read.jsonl (read), Dateien: 5000
B: answers.jsonl (ask), Dateien: 5000
Dateien in beiden: 5000; nur in A: 0; nur in B: 0; nicht vergleichbar: 700
Dateien mit Abweichung: 610; nur gezählt: 0
hazard_codes: dazugekommen 12, weggefallen 85, geändert 140
    /data/sheets/reiniger.pdf
      A: ["H315"]
      B: ["H315", "H319"]
wording: dazugekommen 0, weggefallen 0, geändert 96
    /data/sheets/lack.pdf [P102]
      A: ["Darf nicht in die Hände von Kindern"]
      B: ["Darf nicht in die Hände von Kindern gelangen."]
```

| Angabe | Bedeutung |
| --- | --- |
| dazugekommen | A hat keinen Wert, B hat einen |
| weggefallen | A hat einen Wert, B hat keinen |
| geändert | beide haben einen Wert, und die beiden weichen ab |

Eine Datei zählt je Feld einmal, gleich wie viele ihrer Sätze abweichen. Im
Text ist ein langer Wert nach 220 Zeichen gekürzt; `--json` und `--details`
enthalten ihn ganz. Eine Zeile von `--details`:

```json
{"file": "/data/sheets/reiniger.pdf", "differences": [{"field": "hazard_codes", "a": ["H315"], "b": ["H315", "H319"]}, {"field": "wording", "code": "P102", "a": ["Darf nicht in die Hände von Kindern"], "b": ["Darf nicht in die Hände von Kindern gelangen."]}]}
```

## Das Programm gegen ein Modell

```bash
sdb-reader diff read.jsonl answers.jsonl --details differences.jsonl
```

Jede Abweichung ist eine Stelle zum Nachsehen, im PDF selbst. Wo das Modell
recht hat, hat das Programm einen Lesefehler; wo das Programm recht hat,
folgt nichts. Die Antworten sind behalten, also läuft nach einer Änderung am
Programm nur `read` neu, und dieselben Antworten zeigen, ob die Änderung
getan hat, was sie sollte.

## Das Programm vor und nach einer Änderung

```bash
sdb-reader read sheets/ --output before.jsonl --jobs 8
sdb-reader read sheets/ --output after.jsonl --jobs 8
sdb-reader diff before.jsonl after.jsonl
```

Den ersten Lauf macht das Programm, wie es war, den zweiten das geänderte.
Exit-Code 0 sagt, dass die Änderung keine Lesung verändert hat. Sonst zeigen
die Zahlen, wie weit die Änderung reicht: Eine Regel für einige Blätter, die
Hunderte ändert, ist zu weit.

## Dateien, die nur gezählt werden

```bash
sdb-reader diff before.jsonl after.jsonl --count-only-from held-back.txt
```

Ein Teil eines Bestands, den sich bei der Arbeit am Programm niemand ansehen
soll, lässt sich trotzdem zählen. `--count-only-from DATEI` nennt diese
Dateien, je Zeile eine: einen Dateinamen, einen absoluten Pfad oder das Ende
eines Pfads wie `lieferant-a/reiniger.pdf`. Leere Zeilen und Zeilen, die mit
`#` beginnen, zählen nicht. Eine solche Datei wird je Feld in einer eigenen
Gruppe gezählt und steht in keinem Beispiel und in keiner Zeile von
`--details`:

```text
Dateien mit Abweichung: 41; nur gezählt: 5
revision_date: dazugekommen 38, weggefallen 0, geändert 3
revision_date, nur gezählt: dazugekommen 4, weggefallen 0, geändert 1
```

So zeigen die zurückgehaltenen Dateien, ob eine Änderung auch an Blättern
hält, an denen sie nicht entstanden ist, und niemand bekommt sie zu sehen.
Um sie ganz aus einem Lauf herauszuhalten, haben `read` und `ask`
`--exclude-from`.

## Warnungen

Der Befehl vergleicht, was er bekommt, und sagt auf der Fehlerausgabe, wenn
die beiden Läufe schlecht zueinander passen:

| Warnung | Bedeutung |
| --- | --- |
| verschiedene Lese-Stufen | den Text der PDFs haben verschiedene Fassungen gelesen; Abweichungen können vom Text kommen statt vom Lesen |
| verschiedene Modelle | zwei Läufe von `ask` haben verschiedene Modelle gefragt; das kann gerade das sein, was Sie vergleichen wollen |
| nicht dieselbe Frage | zwei Läufe von `ask` sind mit verschieden formulierten Fragen entstanden |

Eine Warnung ändert den Exit-Code nicht.

## Exit-Codes

| Exit-Code | Bedeutung |
| --- | --- |
| 0 | keine Datei weicht in einem verglichenen Feld ab |
| 1 | mindestens eine Datei weicht ab, gezeigt oder nur gezählt |
| 2 | ein Lauf lässt sich nicht lesen, mischt Datensätze von `read` und `ask` oder enthält keinen, oder die Dateien lassen sich nicht zuordnen; es wurde nichts verglichen |

Dateien, die nur ein Lauf nennt, ändern den Exit-Code nicht.
