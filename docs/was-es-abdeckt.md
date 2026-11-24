# Was es abdeckt

Ein Sicherheitsdatenblatt sieht aus wie ein Formular: sechzehn nummerierte
Abschnitte, eine Kennzeichnung unter 2.2. In Wirklichkeit setzt die Software
jedes Lieferanten es anders, das Recht dahinter hat sich seit 2010
mehrmals geändert, und eine Kennzeichnung druckt ihre Piktogramme als Code,
als Bild oder beides. Diese Seite zählt auf, womit der Leser umgeht, jeder
Punkt in der Form *das Blatt tut dies, der Leser tut das*. Die Nummern in
Klammern nennen die Regeln dahinter; sie stehen in [specs/](../specs/README.md).
Wie eine Datei Schritt für Schritt durch die Bibliothek läuft, erzählt
[How it works](how-it-works.md) (Englisch).
English: [What it handles](what-it-handles.md).

## Die Datei

- **Nicht jede Datei, die Sicherheitsdatenblatt heißt, ist eines.** Der
  Leser ordnet jede Datei einer von vier Arten zu: deutsches
  Sicherheitsdatenblatt, Sicherheitsinformation (eine Unterlage im Aufbau
  eines Blatts, die sich nicht so nennt), Sicherheitsdatenblatt in anderer
  Sprache oder Dokument. Ein Titel mit Tippfehler zählt noch; ein Satz, der
  ein Sicherheitsdatenblatt nur erwähnt, ist kein Titel (SDB-59, SDB-66,
  SDB-68, SDB-105, SDB-140, SDB-141).
- **Mehrere Blätter in einer Datei.** Länderfassungen, ein Set mit einem
  Blatt je Bestandteil: Der Leser findet jedes Blatt (eine Änderungsliste
  ist keines), liest jedes für sich und die Datei als Ganzes, sagt, ob die
  Blätter zum selben Produkt gehören und welches das älteste ist, und
  überspringt ein Deckblatt (SDB-2, SDB-118, SDB-138, SDB-139, SDW-36,
  SDW-45).
- **Scans.** Eine Datei ohne Textschicht liest er per Texterkennung, ebenso
  eine einzelne gescannte Seite in einer Datei, deren übrige Seiten Text
  haben (SDB-46, SDB-95, SDB-116).
- **Eine Textschicht in seltsamer Reihenfolge.** Der Leser setzt die Wörter
  in die Reihenfolge des Drucks zurück, hält Tabellen und Spalten
  auseinander, fügt am Zeilenende getrennte Wörter zusammen und Wörter, die
  eine Datei in Stücken zeichnet (SDB-32, SDB-42 bis SDB-45, SDB-54,
  SDB-99).
- **Überschriften in vielen Formen.** „ABSCHNITT 2“, „2.“, „2:“, mit einer
  Marke für einen geänderten Abschnitt, und die Reihenfolge der Abschnitte
  aus der Zeit vor REACH, als Zusammensetzung und Gefahren getauscht waren
  (SDB-1, SDB-58, SDB-89, SDB-152, SDB-175).
- **Eine Datei in der Datei.** Manche PDFs tragen die Daten des Blatts als
  eSDScom-XML in sich. Der Leser liest sie und stellt sie neben seine
  eigene Lesung (SDW-11).

## Altes und neues Recht

Unter den Blättern hat sich das Recht zweimal geändert. Bis 2015 wurden
Gemische nach den Richtlinien 67/548/EWG und 1999/45/EG eingestuft, mit
R- und S-Sätzen und orangefarbenen Gefahrensymbolen; seitdem nach der
CLP-Verordnung, mit H- und P-Sätzen und rot umrandeten Piktogrammen. Das
Format des Blatts änderte sich mit der Verordnung (EU) 2015/830, deren
Übergangszeit am 31.05.2017 endete, und erneut mit 2020/878.

- **Drei Arten von Blättern.** Ein Blatt der Regeln vor Juni 2017 liest
  der Leser ohne Kennzeichnung, und es bekommt nur die Befunde zu seinem
  Alter. Ein Blatt ab Juni 2017, das noch nicht im Format von 2020/878
  steht, liest er ganz, und es bekommt alle Befunde, neben dem, dass es
  erneuert werden muss. Ein Blatt nach 2020/878 liest er ganz (SDB-216,
  SDW-7, SDW-9, SDW-49).
- **Zwei Einstufungen auf einem Blatt.** Ein Blatt der Übergangszeit kann
  das Produkt nach den alten Richtlinien „nicht kennzeichnungspflichtig“
  nennen und nach CLP einstufen. Für ein Blatt der alten Regeln sagt der
  Leser deshalb, ob das Produkt ein Blatt braucht, sei *nicht nach
  geltendem Recht geprüft* (SDB-218).
- **Alte Sätze ergeben keine Codes.** R- und S-Sätze werden nicht zu H-
  und P-Sätzen, und der alte Satz „Sicherheitsdatenblatt auf Anfrage für
  berufsmäßige Verwender erhältlich“ ist kein EUH210 (SDB-73, SDB-120,
  SDB-123).
- **Die orangefarbenen Symbole der alten Richtlinien sind keine
  Piktogramme** und werden bewusst keinem zugeordnet (SDB-207).

## Die Kennzeichnung

- **Wo sie beginnt und endet.** „Kennzeichnungselemente“, „Kennzeichnung
  nach GHS“, „Etiketteninhalt“, „GHS-Kennzeichnung“ beginnen alle eine
  Kennzeichnung; sie endet an Abschnitt 2.3, außer dort folgen noch
  Elemente der Kennzeichnung. Kopf und Fuß einer Seite gehören nicht dazu
  (SDB-4, SDB-156, SDB-202, SDB-205, SDB-209).
- **Mehr als eine Kennzeichnung.** Eine Kennzeichnung für Verpackungen mit
  höchstens 125 ml, ein Block nach der Biozid- oder der
  Detergenzienverordnung: jede bleibt für sich, wie gedruckt, mit dem, was
  sie weglässt (SDB-188, SDB-189, SDB-190).
- **Bedingungen.** „Obige Kennzeichnung gilt bei Abgabe an privaten
  Endverbraucher“ und Bedingungen für einzelne Sätze bleiben bei der
  Kennzeichnung und werden nicht mit ihr vermischt (SDB-191, SDB-192).
- **Sätze ohne Code.** Druckt die Kennzeichnung einen Satz ohne seinen
  Code, nennt der Leser den Code nach dem Wortlaut der Verordnung und sagt,
  dass er zugeordnet und nicht gedruckt ist (SDB-6, SDB-28, SDB-163,
  SDB-174, SDW-43).
- **Die Formen, in denen Codes kommen.** Sätze mit Lücke („Enthält …
  Kann allergische Reaktionen hervorrufen.“), verbundene Sätze
  („P305+P351+P338“), Listen von Codes ohne Text, „H 315“ mit Leerzeichen,
  H360 und H361 mit den Buchstaben ihrer Wirkung, ein Code mitten in
  seinem eigenen Satz (SDB-30, SDB-52, SDB-64, SDB-121, SDB-125, SDB-155,
  SDB-164).
- **Der Wortlaut des Blatts neben dem der Verordnung.** Für jeden Satz gibt
  die Lesung beide und sagt, wo sie abweichen (SDB-18, SDW-5, SDW-50).
- **Was nicht zur Kennzeichnung gehört.** Ein Code in einem
  Einstufungseintrag („Aquatic Chronic 1, H410“), ein Satz, der im
  Fließtext eine Wirkung beschreibt, der Satz über eine mit einem Biozid
  behandelte Ware: Keiner davon ist ein Satz der Kennzeichnung (SDB-5,
  SDB-41, SDB-196, SDB-219).

## Piktogramme

- **Code, Bild oder beides.** Eine Kennzeichnung nennt ein Piktogramm als
  „GHS07“, zeigt es als Bild oder tut beides; die Lesung sagt es für jedes
  (SDB-179, SDB-211).
- **Bilder aus der PDF-Datei.** Eine eigene Stufe findet die Rauten auf der
  Seite und vergleicht jede mit den neun Piktogrammen der Verordnung
  (BIB-24).
- **Farbig, schwarz oder grau.** REACH erlaubt auf dem Blatt ein
  schwarz-weißes Piktogramm; der Leser findet rote, schwarze und graue
  Rahmen (SDB-212).
- **In Stücken gezeichnet.** Manche Dateien setzen ein Piktogramm aus
  schmalen Streifen zusammen; Piktogramme, die sich berühren, werden
  getrennt (SDB-208).
- **Auf gescannten Seiten,** wo die Kennzeichnung über die Lage der Wörter
  gefunden wird, die die Texterkennung liest (SDB-204).
- **Kleine oder ungewöhnliche Zeichnungen.** Eine Raute, die zuerst keinem
  zugeordnet wird, wird feiner noch einmal angesehen; die Flamme (GHS02)
  und die Flamme über einem Kreis (GHS03) unterscheidet der Ring; ein
  anders gezeichnetes, aber eindeutig ähnlichstes Piktogramm wird benannt
  (SDB-206, SDB-213, SDB-215).
- **Codes, die die Texterkennung falsch liest,** wie „GHS007“ oder
  „GHS 05“ (SDB-203).
- **Piktogramme in Abschnitt 2.1** gehören zur Einstufung; sie zählen nur,
  wo keine Kennzeichnung gefunden wird (SDB-202).

## Produkt, Lieferant, Einstufung und Daten

- **Die Einstufung** steht in vielen Formulierungen, als Gefahrenklasse
  oder als Satz, das Produkt sei nicht eingestuft; ein Nebensatz einer
  Bedingung („… selbst wenn sie als gefährlich eingestuft wurden“) stuft
  nicht ein (SDB-75, SDB-80, SDB-81, SDB-107, SDB-214).
- **Der Produktname** kommt aus Abschnitt 1.1, nicht aus einer
  Artikelnummer, einer Rezepturnummer oder einem Verweis; fehlt er dort,
  aus dem Kopf des Blatts (SDB-131, SDB-148 bis SDB-150, SDB-153, SDB-158).
- **Der Lieferant** steht unter vielen Bezeichnungen; nennt ein Block
  mehrere Firmen, gilt die deutsche. Die Notrufnummer wird vom Telefon des
  Lieferanten unterschieden, und die Nummer eines Giftnotrufs ist nie die
  des Lieferanten (SDB-49, SDB-50, SDB-55, SDB-117, SDB-132 bis SDB-136).
- **Daten** kommen mit dem Monat als Wort, mit dem Jahr zuerst, mit dem
  Monat zuerst, mit Wochentag, mit einem über die Zeile getrennten Wort;
  ein Datum in der Zukunft ist kein Datum; eine Datei mit mehreren Blättern
  hat das neueste ihrer Daten (SDB-57, SDB-90, SDB-128, SDB-129, SDB-137,
  SDB-161, SDB-182, SDB-201).
- **Die Version** ist die Nummer, die die Datei am häufigsten nennt, ohne
  die als ersetzt bezeichneten; die Länder, für die das Blatt ausgestellt
  ist, sind DE, AT und CH (SDB-20, SDB-69).
- **Das geltende Blatt** unter mehreren eines Produkts wählt die Bibliothek
  nach Datum, Land und Version (BIB-6 bis BIB-9).

## Befunde

Wo ein Blatt hinter der CLP-Verordnung oder REACH zurückbleibt, sagt der
Leser das als Befund neben der Lesung: ein eingestuftes Produkt ohne
Kennzeichnung, ein Satz der Kennzeichnung, den die Einstufung nicht nennt,
oder umgekehrt, ein Signalwort, das den Codes widerspricht, ein Piktogramm,
das einem anderen weichen müsste, ein Satz in anderem Wortlaut als dem der
Verordnung, eine Einstufung, die der Kennzeichnung widerspricht, ein Blatt,
das erneuert werden muss, Blätter verschiedener Produkte in einer Datei
(SDB-79, SDB-170 bis SDB-173, SDB-181, SDB-197, SDB-199, SDW-7, SDW-9,
SDW-36, SDW-42).

- **Nur, wo er sicher ist.** Hängt die Antwort an etwas, das das Blatt
  nicht sagt, etwa der Größe der Verpackung oder wer das Produkt kauft,
  gibt es keinen Befund (SDB-169, SDB-183, SDB-193, SDB-194).
- **Einzeln geprüft.** Die Befunde, dass einer Kennzeichnung etwas fehlt
  oder sie etwas trägt, das sie nicht tragen sollte, werden vor einer
  Veröffentlichung Fall für Fall an einem Bestand von etwa 14.850 Blättern
  geprüft. Viele Fälle erwiesen sich als Lesefehler und wurden im Leser
  behoben; ein Befund prüft also auch die Lesung.

## Sicher voreingestellt

- **Eine unvollständige Kennzeichnung wird zurückgehalten.** Fehlt einer
  Kennzeichnung sicher, was sie zeigen muss, gibt die Lesung sie nur auf
  Nachfrage aus, damit kein Programm ein gefährliches Produkt aus Versehen
  ohne seine Warnungen zeigt (SDB-217, BIB-26).
- **Drei Antworten auf „braucht das Produkt ein Blatt?“**: ja, nein oder
  nicht nach geltendem Recht geprüft (SDB-76, SDB-142, SDB-154, SDB-218).
- **Dieselbe Datei ergibt dasselbe Ergebnis.** Kein Sprachmodell und keine
  Uhr: Was vom heutigen Tag abhängt, bekommt ihn vom Aufrufer (BIB-19).

Was der Leser noch nicht kann, steht unter „Grenzen“ in der
[README](https://github.com/foerdebaumarkt/sdb-reader/blob/main/README.de.md#grenzen)
und unter „Offene Fragen“ in den Specs.
