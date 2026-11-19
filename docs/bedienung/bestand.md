# Einen ganzen Bestand lesen

Ein Ordner mit tausenden Blättern ist ein anderer Auftrag als eine Datei: Er
dauert, er kann unterbrochen werden, und bei `ask` kostet jede Anfrage
Zeit und Geld. Dafür haben `read` und `ask` dieselben vier Optionen.

## Ordner statt Dateien

```bash
sdb-reader read sheets/
sdb-reader read sheets/ more/extra.pdf
```

Ein Ordner steht für jede Datei mit der Endung `.pdf` in ihm und in seinen
Unterordnern, in der Reihenfolge der sortierten Pfade. Dateien und Ordner
lassen sich mischen; eine Datei, die zweimal vorkommt, wird einmal gelesen.
Ein Ordner ohne ein einziges PDF beendet den Befehl mit Exit-Code 2, bevor
er etwas liest.

## Eine Ergebnisdatei, die mitwächst

```bash
sdb-reader read sheets/ --output run.jsonl
```

Ohne `--output` kommt das Ergebnis als eine Liste am Ende, und ein Abbruch
kurz davor kostet alles. Mit `--output DATEI` schreibt der Befehl für jede
Datei eine Zeile in DATEI, sobald sie fertig ist. Jede Zeile ist der
Datensatz dieser Datei, derselbe wie in der Liste. Das Format heißt JSON
Lines; viele Programme lesen es Zeile für Zeile.

Gibt es DATEI schon, lehnt der Befehl den Lauf ab, statt sie zu überschreiben.

## Einen Lauf fortsetzen

```bash
sdb-reader read sheets/ --output run.jsonl --resume
```

`--resume` setzt einen Lauf fort, der abgebrochen wurde: Der Befehl liest
DATEI, lässt jede Datei aus, deren Zeile schon darin steht, und hängt die
übrigen an. Derselbe Aufruf kann also beliebig oft wiederholt werden, bis er
durch ist.

- Eine Datei gilt als dieselbe, wenn Pfad und Größe mit ihrer Zeile
  übereinstimmen. Eine ersetzte Datei wird neu gelesen; ihre alte Zeile
  bleibt stehen, und es gilt die letzte Zeile, die eine Datei nennt.
- Eine Datei, die gescheitert ist und deshalb keine Zeile hat, wird beim
  Fortsetzen neu versucht.
- Wurde der Lauf mitten in einer Zeile hart beendet, entfernt `--resume`
  die halbe Zeile und sagt es.

Mit Strg-C lässt sich ein Lauf jederzeit abbrechen. Der Befehl sagt, wie
weit er kam, und endet mit Exit-Code 130; die Ergebnisdatei enthält nur
ganze Zeilen.

## Mehrere Dateien zugleich

```bash
sdb-reader read sheets/ --output run.jsonl --jobs 8
```

`--jobs N` lässt den Befehl an N Dateien zugleich arbeiten, `read` in N
Prozessen, `ask` mit N Anfragen, die gleichzeitig laufen. Für `read` ist
die Zahl der Prozessorkerne ein guter Wert. Für `ask` bestimmt der
Dienst, wie viele Anfragen er zugleich annimmt.

Was der Befehl zu einer Datei ausgibt, hängt davon nicht ab. Nur die
Reihenfolge der Zeilen in der Ergebnisdatei folgt dann dem Fertigwerden,
nicht der Angabe. Die Liste ohne `--output` bleibt in der Reihenfolge der
Angabe.

## Dateien ausnehmen

```bash
sdb-reader read sheets/ --exclude-from held-back.txt
```

`--exclude-from DATEI` nimmt Dateien aus dem Lauf: DATEI nennt je Zeile
einen Dateinamen, einen Pfad relativ zu einem der angegebenen Ordner oder
einen absoluten Pfad. Leere Zeilen und Zeilen, die mit `#` beginnen, zählen
nicht.

```text
# zurückgehalten
farbe.pdf
lieferant-a/reiniger.pdf
```

Eine ausgenommene Datei wird nicht gelesen, nicht an ein Modell geschickt
und steht nicht im Ergebnis. So bleibt ein Teil eines Bestands, den niemand
ansehen soll, aus jedem Lauf heraus, ohne dass man ihn umräumen muss.

## Was der Befehl unterwegs und am Ende sagt

Bei mehr als einer Datei schreibt der Befehl auf die Fehlerausgabe, wie weit
er ist, höchstens alle 15 Sekunden, und am Ende eine Zeile über den Lauf:

```text
[sdb-reader] 1200 von 5000 Dateien fertig, gescheitert: 2
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gescheitert: 3
```

| Angabe | Bedeutung |
| --- | --- |
| Dateien | so viele Dateien hatte der Lauf, ohne die ausgenommenen |
| früher erledigt | so viele hat `--resume` ausgelassen, weil ihre Zeile schon da war |
| ausgenommen | so viele hat `--exclude-from` herausgenommen |
| gescheitert | so viele ließen sich nicht lesen, oder ihre Anfrage scheiterte |

## Ein Modell zum ganzen Bestand fragen

```bash
sdb-reader ask sheets/ --output answers.jsonl --jobs 4 --retries 3
sdb-reader diff read.jsonl answers.jsonl
```

Für `ask` kommen zwei Dinge dazu, siehe [Ein Sprachmodell fragen](fragen.md).

`--retries N` stellt eine Anfrage, die scheitert, weil der Dienst überlastet
oder kurz nicht erreichbar ist, bis zu N-mal neu, mit wachsender Wartezeit
von höchstens einer Minute. Ohne die Option wird keine Anfrage wiederholt.
Jeder andere Fehler, etwa ein falscher Schlüssel, scheitert sofort.

Nennt der Dienst, wie viele Token eine Anfrage gekostet hat, steht das im
Datensatz unter `usage`, und die Zeile am Ende zählt zusammen:

```text
[sdb-reader] Dateien: 5000; früher erledigt: 0; ausgenommen: 500; gefragt: 4300; gescheitert: 3; Token gesendet: 5200000, empfangen: 1050000
```

Was das in Geld ist, rechnet der Befehl nicht aus; die Preise nennt der
Dienst. Ein Probelauf über hundert Blätter zeigt, was ein Blatt im Mittel
kostet und wie lange es dauert, bevor der ganze Bestand läuft.

Die Antworten bleiben in der Ergebnisdatei. `diff` stellt sie neben einen
Lauf von `read`, so oft wie nötig und ohne neu zu fragen, siehe
[Zwei Läufe vergleichen](laeufe-vergleichen.md).
