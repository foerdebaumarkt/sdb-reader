# Was es abdeckt

Zu jedem Produkt mit gefährlichen Inhaltsstoffen, etwa einer Farbe, einem
Kleber oder einem Reiniger, gibt es ein Sicherheitsdatenblatt: ein
Pflichtdokument, das sagt, wie gefährlich das Produkt ist und wie man sicher
damit umgeht. Jeder Hersteller gestaltet es anders, die Vorschriften haben
sich mehrmals geändert, und manches steht nur als Bild darin. sdb-reader
liest diese PDF-Dateien und macht daraus verlässliche Daten.
English: [What it handles](what-it-handles.md).

## Dateien

- **Tausende Dateien auf einmal.** Ein ganzer Ordner wird in einem Lauf
  gelesen.
- **Auch Scans.** Eingescannte Blätter werden per Texterkennung gelesen.
- **Erkennt, was eine Datei ist.** Nicht alles, was Sicherheitsdatenblatt
  heißt, ist eines. Blätter in anderer Sprache und andere Dokumente werden
  erkannt und nicht als deutsches Blatt gelesen.
- **Mehrere Blätter in einer Datei.** Manche Dateien enthalten Blätter für
  mehrere Länder oder für jedes Teil eines Sets. Jedes wird für sich
  gelesen.

## Warnhinweise und Symbole

- **Die Warnhinweise des Produkts,** etwa „Verursacht Hautreizungen“, mit
  dem Wortlaut des Blatts und dem amtlichen Wortlaut daneben.
- **Gefahrensymbole, auch als Bild.** Die rot umrandeten Rauten werden
  erkannt, auch wenn sie nur als Bild gedruckt sind, ob farbig, grau oder
  eingescannt.
- **Sonderfälle bleiben getrennt.** Für sehr kleine Packungen und für
  bestimmte Produktgruppen gelten eigene Angaben. Sie werden nicht mit den
  übrigen vermischt.

## Produktangaben

- **Produkt, Hersteller, Kontakt und Notrufnummer.**
- **Datum und Version,** in den vielen Schreibweisen, die Hersteller
  verwenden.
- **Das geltende Blatt.** Liegen zu einem Produkt mehrere Blätter vor, wählt
  sdb-reader das aktuelle.

## Alt und neu

- **Veraltete Blätter werden erkannt.** Ein Blatt nach Vorschriften, die
  seit Mitte 2017 nicht mehr gelten, wird als solches gekennzeichnet; seine
  Warnhinweise werden nicht als gültig ausgegeben.
- **Fällige Erneuerung.** Ein Blatt, das zwar gilt, aber nicht dem neuesten
  Stand entspricht, wird gemeldet.

## Fehler im Blatt

- **Meldet Fehler des Herstellers,** etwa fehlende oder widersprüchliche
  Warnhinweise oder ein Symbol, das nicht passt.
- **Nur sichere Meldungen.** Hängt eine Frage an etwas, das das Blatt nicht
  sagt, gibt es keine Meldung. Die Meldungen wurden an rund 14.850 echten
  Blättern einzeln geprüft.

## Verlässlich

- **Auf der sicheren Seite.** Sind die Warnhinweise eines Blatts
  unvollständig, gibt sdb-reader sie nicht ungefragt weiter, damit kein
  Produkt aus Versehen ohne seine Warnungen angezeigt wird. Und aus einem
  veralteten Blatt schließt es nicht, ein Produkt sei harmlos.
- **Gleiche Datei, gleiches Ergebnis.** Feste, aufgeschriebene Regeln statt
  KI; jedes Ergebnis ist nachvollziehbar.
- **Auf dem eigenen Rechner.** Keine Cloud, keine Kosten pro Seite.
- **Für Menschen und Programme.** Das Ergebnis gibt es als lesbaren Bericht
  oder als Daten, auf Deutsch oder Englisch. Open Source.

Wie sdb-reader im Einzelnen arbeitet, steht in
[How it works](how-it-works.md) (englisch), die verbindlichen Regeln in
[specs/](../specs/README.md).
