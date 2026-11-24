# sdb-reader

Liest deutsche Sicherheitsdatenblätter nach REACH und CLP aus PDF-Dateien,
ohne Sprachmodell: Dieselbe Datei ergibt immer dasselbe Ergebnis, und jede
Regel, der der Leser folgt, ist aufgeschrieben.

English: [README.md](README.md)

```bash
sdb-reader read sheet.pdf
```

Zu jedem PDF sagt es:

- **was die Datei ist:** ein deutsches Sicherheitsdatenblatt, eine
  Sicherheitsinformation, ein Sicherheitsdatenblatt in einer anderen Sprache
  oder ein anderes Dokument;
- **die Einstufung**, die Abschnitt 2 nennt;
- **die Kennzeichnung:** Signalwort, Piktogramme und die H-, P- und
  EUH-Sätze, mit dem Wortlaut des Blatts neben dem der Verordnung;
- **Daten und Version**, die Länder, für die das Blatt ausgestellt ist, und
  den Lieferanten;
- **was an dem Blatt als Dokument zu beanstanden ist:** vor 2021
  überarbeitet, kein lesbares Datum, Einstufung und Kennzeichnung, die sich
  widersprechen, ein Satz, der im Wortlaut von der Verordnung abweicht.

Das Ergebnis ist JSON. Warnungen und Befunde kommen als fester Code mit
einem Satz, auf Deutsch oder Englisch. Wer ein Blatt selbst lesen will,
bekommt dasselbe mit `show` als Bericht:

```bash
sdb-reader show sheet.pdf
```

Hinter diesen wenigen Punkten stehen viele Fälle: mehrere Blätter in einer
Datei, Scans, Kennzeichnungen für kleine Verpackungen, Piktogramme nur als
Bild, Blätter nach altem Recht neben denen nach neuem. [Was es
abdeckt](docs/was-es-abdeckt.md) zählt sie auf.

## Warum nicht einfach das PDF einem Sprachmodell geben?

Für ein einzelnes Blatt, das man sich selbst ansieht, funktioniert das gut. In
einem Test im November 2026 mit 30 schwierigen Blättern lasen aktuelle große
kommerzielle Modelle Lieferant, Datum und die auf der Kennzeichnung gedruckten
Codes fast fehlerfrei, ebenso die kleineren Modelle derselben Anbieter.
`sdb-reader` ist für den Fall gedacht, dass man viele Blätter liest und nach
dem Ergebnis handelt: entscheiden, ob ein Produkt verkauft werden darf, einen
Shop oder eine Datenbank füllen, die Blätter eines Lieferanten prüfen. Dann
zählt, was ein Modell nicht liefert:

- **Eine Regel statt des Urteils eines Modells.** Viele Kennzeichnungen
  drucken manche Sätze nur als Satz, ohne Code. Nach „den Codes“ gefragt,
  nennt ein Modell den Code eines solchen Satzes, ein anderes lässt ihn weg,
  ein drittes rät: Im selben Test nannte ein offenes Modell für ein Spray
  sechs Sicherheitshinweise, die dessen Kennzeichnung nicht druckt, und bei
  einem zweiten Lauf mit derselben Eingabe keinen. `sdb-reader` wendet eine
  feste Regel an und sagt zu jedem Code, ob das Blatt ihn druckt oder der
  Leser ihn dem Satz zugeordnet hat.
- **Dasselbe Blatt, dieselbe Antwort.** Ein Modell kann beim zweiten Mal
  anders antworten. `sdb-reader` liest eine Datei jedes Mal gleich; ein
  Ergebnis, nach dem man heute handelt, gilt auch morgen.
- **Jeder Wert ist nachvollziehbar.** Jede Angabe einer Lesung folgt aus einer
  nummerierten, getesteten Regel. Eine falsche Lesung ist eine Regel, die man
  berichtigt, keine Frage, die man noch einmal stellt.
- **Tausende Blätter, ohne Kosten je Seite, offline.** Ein großes
  kommerzielles Modell kostet einige Cent je Blatt; ein Modell auf dem eigenen
  Rechner kostet Zeit und ist weniger zuverlässig. `sdb-reader` läuft auf
  einem gewöhnlichen Rechner und schickt kein Blatt irgendwohin.
- **Ein festes Format mit Befunden.** Das Ergebnis ist JSON mit
  veröffentlichtem Schema, mit festen Codes für jede Warnung und jeden Befund,
  auch dafür, wo ein Blatt hinter der CLP-Verordnung zurückbleibt.

**Welches Modell es braucht.** Wer trotzdem ein Modell nimmt: Aktuelle Modelle
der großen Anbieter lesen Blätter sehr gut, auch deren kleine und günstige.
Offene Modelle auf dem eigenen Rechner schnitten im selben Test deutlich
schlechter ab, selbst auf einem Arbeitsplatzrechner der Spitzenklasse mit 128
GB Speicher, dem Höchsten, was gewöhnliche Desktop- und Notebook-Rechner
bieten (getestet wurden Modelle mit rund 27 Milliarden Parametern und ein
größeres Mixture-of-Experts-Modell). Sie lesen gedruckte Codes zuverlässig,
aber wo eine Kennzeichnung nur Sätze druckt, lassen sie Sätze weg oder raten.
Offene Modelle, die für einen solchen Rechner zu groß sind, wurden nicht
getestet. Verlangt man zu jedem Satz ein wörtliches Zitat und prüft es gegen
den Text, fallen die meisten geratenen Codes heraus, aber auch richtige, wo
das Blatt einen Satz anders formuliert als die Verordnung. (Stand 2026;
Modelle ändern sich schnell.)

`sdb-reader ask` legt ein Blatt einem Modell eigener Wahl vor und hält dessen
Antwort neben der Lesung fest, sodass sich beide vergleichen lassen. Mehr dazu
in [How it works](https://foerdebaumarkt.github.io/sdb-reader/latest/how-it-works.html)
(Englisch).

**Die Idee dahinter.** Der Leser gibt wieder, was ein Blatt druckt, und meldet
getrennt davon, wo das Blatt hinter der Verordnung zurückbleibt; was daraus
folgt, entscheidet, wer ihn benutzt. [How it
works](https://foerdebaumarkt.github.io/sdb-reader/latest/how-it-works.html)
(Englisch) beschreibt die Grundsätze dahinter.

## Dokumentation

Die Dokumentation steht unter <https://foerdebaumarkt.github.io/sdb-reader/>,
je veröffentlichter Version eine Ausgabe. Dieselben Seiten liegen im
Repository unter [docs/](docs/README.md).

| Sie wollen | Lesen Sie |
| --- | --- |
| den Befehl benutzen und verstehen, was er ausgibt | [Bedienung](docs/bedienung/README.md), auf Englisch: [Using the command line](docs/usage/README.md) |
| Blätter aus einem Python-Programm lesen | [Using the library](docs/api/README.md) (englisch) |
| sehen, womit der Leser umgeht | [Was es abdeckt](docs/was-es-abdeckt.md), auf Englisch: [What it handles](docs/what-it-handles.md) |
| verstehen, wie aus einer Datei eine Lesung wird | [How it works](docs/how-it-works.md) (englisch) |
| am Leser mitarbeiten | [Contributing](docs/contributing/README.md) (englisch) |
| wissen, was eine Version geändert hat | [CHANGELOG.md](CHANGELOG.md) (englisch) |
| die verbindlichen Regeln lesen | [specs/](specs/README.md) |

## Installation

Braucht Python 3.12 oder neuer. Installiert wird es aus dem Python Package
Index:

```bash
uv tool install sdb-reader
```

Gescannte Blätter werden per Texterkennung gelesen; dafür braucht es
`tesseract` mit deutschen Sprachdaten. Die Einzelheiten stehen unter
[Installation](docs/bedienung/installation.md).

## Grenzen

- Nur deutsche Blätter. Ein Blatt in einer anderen Sprache wird als solches
  erkannt und nicht gelesen.
- Es liest eine Datei nach der anderen. Welche Blätter zu einem Produkt
  gehören, weiß das Programm, das es benutzt; die Bibliothek wählt dann unter
  ihnen das geltende.
- Ob ein Produkt ein Sicherheitsdatenblatt braucht, wird aus Einstufung und
  Kennzeichnung gelesen. Abschnitt 2.3 (PBT, vPvB, Kandidatenliste) wird
  nicht gelesen.
- Ein älteres Blatt in einer anderen Sprache ohne nummerierte
  Unterabschnitte zählt als Dokument.
- Ein Formular in zwei Spalten ohne Doppelpunkte wird nur in Abschnitt 1 als
  Bezeichnung und Wert gelesen. In den übrigen Abschnitten eines solchen
  Blatts wird ein Wert womöglich nicht gefunden.

## Lizenz

GNU Affero General Public License, Version 3 oder später ([LICENSE](LICENSE)).
Die PDF-Bibliothek, auf der der Leser aufbaut, PyMuPDF (installiert als
`pymupdf-lite`), steht unter der AGPL;
ein Programm, das dieses Paket benutzt, übernimmt deren Pflichten.

Copyright © 2026 Förde-Baumarkt Holger Claussen GmbH & Co. KG
(<service@foerde-baumarkt.de>).
[NOTICE](NOTICE) nennt den Rechteinhaber und die Quelle des Wortlauts der
Verordnung, den das Paket mitbringt.
