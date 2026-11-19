# Blätter als Bericht anzeigen

`show` liest Dateien genau wie [`read`](lesen.md) und gibt aus, was es
gefunden hat: als Bericht zum Lesen, nicht als JSON. Es ist für alle, die
sich ein Blatt selbst ansehen wollen. Ein Programm, das mit dem Ergebnis
arbeitet, nimmt `read`.

## Eine Datei, mehrere Dateien, ein Ordner

```bash
sdb-reader show sheet.pdf
sdb-reader show sheet.pdf other.pdf
sdb-reader show folder/
sdb-reader show folder/ folder/sheet.pdf
```

Eine Datei, die Sie nennen, bekommt den vollen Bericht. Ein Ordner bekommt
eine Zeile für jedes PDF in ihm und seinen Unterordnern. Dateien und Ordner
lassen sich mischen: Eine Datei, die selbst genannt ist und zugleich in
einem angegebenen Ordner liegt, bekommt den vollen Bericht. Hat der Aufruf
mehr als eine Datei, zählt eine Schlusszeile sie.

## Der Bericht einer Datei

```text
musterlack.pdf
  Sicherheitsdatenblatt, deutsch, 1 Blatt

  Produkt        Musterlack seidenmatt
  Lieferant      Nordwerk GmbH, Hafenstraße 1, 24000 Musterstadt
  Kontakt        +49 30 0000000, info@nordwerk.example
  Notruf         Giftnotruf: +49 30 19240
  Überarbeitet   12.03.2019 (Version 4.1)

  Kennzeichnung  Achtung · GHS07
    H317  Kann allergische Hautreaktionen verursachen.
    P280  Schutzhandschuhe tragen.
    EUH208  Enthält Musterstoff. Kann allergische Reaktionen hervorrufen.

  Braucht ein Sicherheitsdatenblatt: ja

  Hinweise
    - Überarbeitet am 12.03.2019, vor dem 01.01.2021: Das Blatt kann Anhang II der REACH-Verordnung in der Fassung der Verordnung (EU) 2020/878 nicht erfüllen.
```

Von oben nach unten:

| Teil | Was er sagt |
| --- | --- |
| erste Zeile | die Datei, wie Sie sie genannt haben |
| zweite Zeile | was die Datei ist; bei einem deutschen Sicherheitsdatenblatt, wie viele Blätter sie hält |
| `Produkt`, `Lieferant` | der Produktname und Name und Anschrift des Lieferanten, wie das Blatt sie druckt |
| `Kontakt` | Telefonnummer und E-Mail-Adresse des Lieferanten. Nennt das Blatt für die auskunftgebende Stelle eine andere Adresse, folgt sie als `Auskunft: …` |
| `Notruf` | die Notrufnummer, wie das Blatt sie druckt |
| `Überarbeitet` | das Überarbeitungsdatum und in Klammern die Version des Blatts. Nennt ein Blatt nur ein Ausgabedatum, steht es unter `Ausgegeben` |
| `Kennzeichnung` | das Signalwort und die Piktogramme, darunter jeder H-, P- und EUH-Satz der Kennzeichnung mit dem Wortlaut des Blatts. Druckt das Blatt einen Code ohne Worte, steht der Wortlaut der Verordnung |
| `Braucht ein Sicherheitsdatenblatt` | ob das Produkt nach Einstufung und Kennzeichnung ein Sicherheitsdatenblatt braucht. Eine Zeile darunter sagt es, wenn das Blatt sich freiwillig oder sein Produkt ein Erzeugnis nennt |
| `Hinweise` | was an dem Blatt als Dokument zu beanstanden ist und was das Programm beim Lesen bemerkt hat; `keine`, wo es nichts gibt |

Was das Blatt nicht nennt, steht als `nicht genannt` da. Ein Blatt ganz ohne
Kennzeichnung zeigt `keine` hinter `Kennzeichnung`; die Hinweise, die nur
dasselbe noch einmal sagten (kein H-Satz, kein P-Satz), entfallen dann.
`read` gibt sie weiter aus.

Die Sätze unter `Hinweise` sind die Meldungen von `read`:
[Alle Meldungen](meldungen.md) führt sie auf. Die Zweifel, die das Programm
hatte, als es die Datei als Blatt annahm, und die Daten, die manche PDFs
eingebettet tragen, stehen nicht im Bericht. `read` hat beides.

## Eine Datei mit mehreren Blättern

```text
set.pdf
  Sicherheitsdatenblatt, deutsch, 2 Blätter
  Vor den Blättern steht ein Deckblatt; es wird nicht gelesen.

  Blatt 1 von 2
    Produkt        Musterkleber Komponente A
    …

  Blatt 2 von 2
    Produkt        Musterkleber Komponente B
    …

  Die Datei als Ganzes
    Braucht ein Sicherheitsdatenblatt: ja

    Hinweise
      - Die Datei enthält 2 Sicherheitsdatenblätter; ihre Kennzeichnungen sind zusammengeführt.
```

Jedes Blatt steht für sich, in der Reihenfolge der Datei, mit den Hinweisen,
die zu ihm gehören. Der letzte Block gilt der Datei: ob das Produkt ein Blatt
braucht, wenn man alle Blätter zusammennimmt, und die Hinweise, die die
Blätter vergleichen oder die Datei betreffen. Ein Deckblatt vor den Blättern
wird genannt und nicht gelesen; nennt es ein Display, steht das Wort dabei.

## Eine Datei, die kein Blatt ist

```text
prospekt.pdf
  Kein Sicherheitsdatenblatt
    - Das Dokument hat weder den Titel noch den Aufbau eines Sicherheitsdatenblatts.
```

Der Bericht sagt, was die Datei ist und warum. Eine Datei, aus der sich kein
Text lesen ließ, steht als `Nicht lesbar` da, mit dem Grund.

## Ein Ordner

```text
ordner/leer.pdf: Nicht lesbar
ordner/musterlack.pdf: Sicherheitsdatenblatt, deutsch, 1 Blatt · Musterlack seidenmatt · 12.03.2019 · 1 Hinweis
ordner/prospekt.pdf: Kein Sicherheitsdatenblatt
ordner/set.pdf: Sicherheitsdatenblatt, deutsch, 2 Blätter · mit Deckblatt · Musterkleber Komponente A (04.05.2023); Musterkleber Komponente B (02.03.2022) · 3 Hinweise

Dateien: 4; Sicherheitsdatenblätter: 2; andere Dokumente: 1; nicht lesbar: 1; mit Hinweisen: 2; ausgenommen: 0
```

Eine Zeile nennt die Datei, was sie ist und, bei einem deutschen
Sicherheitsdatenblatt, das Produkt, das Datum und wie viele Hinweise ihr
voller Bericht hat. Hält eine Datei mehrere Blätter, nennt die Zeile jedes
von ihnen, in der Reihenfolge der Datei und durch Semikolon getrennt, mit
seinem Datum in Klammern, und sagt davor, ob ein Deckblatt davor steht. Um
die Hinweise zu sehen, nennen Sie die Datei selbst.

## Optionen

| Option | Wirkung |
| --- | --- |
| `--max-pages N` | nur die ersten N Seiten jeder Datei lesen; ohne die Option alle Seiten |
| `--jobs N` | an N Dateien zugleich arbeiten; die Berichte bleiben in der angegebenen Reihenfolge |
| `--exclude-from DATEI` | die Dateien auslassen, die DATEI nennt, siehe [Einen ganzen Bestand lesen](bestand.md#dateien-ausnehmen) |
| `--lang de` oder `--lang en` | Sprache des Berichts; ohne Angabe Deutsch |
| `--messages DATEI` | die Wörter des Berichts aus einer eigenen Datei nehmen |

Die letzten beiden sind unter
[Die Ausgabe verstehen](ausgabe.md#meldungen) erklärt. Die Namen, das
Signalwort und die Sätze eines Blatts werden nie übersetzt: Sie stehen, wie
das Blatt sie druckt.

`show` schreibt keine Datei und setzt keinen Lauf fort: `--output`,
`--resume`, `--indent` und `--include-raw-text` gehören zu `read`.

## Exit-Codes und Fehlerausgabe

Die Exit-Codes sind die von [`read`](lesen.md#exit-codes): 0, wenn jede Datei
gelesen wurde, 1, wenn mindestens eine sich nicht lesen ließ, 2, wenn der
Aufruf sich nicht ausführen lässt, 130 nach Strg-C. Eine Datei, die kein
Sicherheitsdatenblatt ist, ist kein Fehlschlag.

Der Bericht geht auf die Standardausgabe. Eine Datei, aus der sich kein Text
lesen lässt, steht mit ihrem Grund im Bericht. Nur eine Datei, an der das
Programm scheitert, wird zusätzlich auf der Fehlerausgabe genannt, mit dem
Fehler.

## Der Text kann sich ändern

Der Bericht ist für Menschen geschrieben. Wortlaut und Aufbau können sich
mit jeder Version ändern, und nichts sollte darauf bauen. Was ein Skript
braucht, steht im Ergebnis von `read`, das ein Schema beschreibt und das
stabil bleibt.
