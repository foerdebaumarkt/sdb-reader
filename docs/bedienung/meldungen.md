# Alle Meldungen

Jede Meldung, die das Programm geben kann, mit ihrem Code, ihren Angaben
und ihrem Satz auf Deutsch. Die Seite schreibt `tools/docs/message_pages.py`
aus der Liste des Programms; sie wird nicht von Hand geändert. Was eine Meldung
ist und wie man ihre Sprache wählt, steht unter [Die Ausgabe verstehen](ausgabe.md#meldungen).

## Text lesen

| Code | Angaben | Satz |
| --- | --- | --- |
| `read-by-ocr-no-text-layer` | – | Das PDF hat keine Textschicht; seine Seiten wurden per Texterkennung gelesen, Abstände können daher falsch sein. |
| `read-by-ocr-single-characters` | – | Die Textschicht des PDF besteht aus einzelnen Zeichen; seine Seiten wurden per Texterkennung gelesen, Abstände können daher falsch sein. |
| `pages-read-by-ocr` | `pages` | Eine Seite ohne Textschicht wurde per Texterkennung gelesen. / {pages} Seiten ohne Textschicht wurden per Texterkennung gelesen. |
| `short-text` | – | Der gelesene Text ist ungewöhnlich kurz; das Dokument ist möglicherweise unvollständig oder gescannt. |

## Warum sich kein Text lesen ließ

| Code | Angaben | Satz |
| --- | --- | --- |
| `pdf-not-found` | – | Die Datei gibt es nicht. |
| `pdf-too-large` | `size_bytes`, `limit_bytes` | Die Datei ist zu groß: {size_bytes} Bytes, gelesen werden höchstens {limit_bytes}. |
| `pdf-unreadable` | `detail` | Die Datei lässt sich nicht als PDF öffnen: {detail} |
| `no-text-layer` | `pages` | Das PDF hat keine Textschicht ({pages} Seite angesehen). / Das PDF hat keine Textschicht ({pages} Seiten angesehen). |
| `no-text` | `pages`, `extractor` | Aus dem PDF ließ sich kein Text lesen ({pages} Seite angesehen, gelesen mit {extractor}). / Aus dem PDF ließ sich kein Text lesen ({pages} Seiten angesehen, gelesen mit {extractor}). |
| `ocr-unavailable` | – | Die Texterkennung steht nicht zur Verfügung: Das Programm tesseract ist nicht installiert. Nötig ist es mit den deutschen Sprachdaten. |
| `ocr-too-old` | `version`, `minimum` | Die Texterkennung steht nicht zur Verfügung: Installiert ist tesseract {version}, nötig ist mindestens Version {minimum}. |
| `ocr-language-missing` | `language` | Die Texterkennung steht nicht zur Verfügung: Dem Programm tesseract fehlen die Sprachdaten „{language}“. |
| `ocr-timeout` | – | Die Texterkennung hat für eine Seite zu lange gebraucht und wurde abgebrochen. |
| `ocr-failed` | `detail` | Die Texterkennung ist gescheitert: {detail} |

## Was die Datei ist

| Code | Angaben | Satz |
| --- | --- | --- |
| `no-title-keywords` | – | Der Text nennt kein Sicherheitsdatenblatt. |
| `no-section-marker` | – | Der Text hat keine Abschnittsüberschrift wie „ABSCHNITT 1“. |
| `no-regulation-reference` | – | Der Text verweist weder auf die REACH- noch auf die CLP-Verordnung. |
| `no-hazard-codes-in-text` | – | Der Text nennt keinen H-Satz mit seiner Nummer (etwa H315). |
| `short-sample` | – | Der Text ist kurz für ein Sicherheitsdatenblatt; das Dokument ist möglicherweise abgeschnitten oder gescannt. |
| `safety-information` | `sections` | Keine Zeile trägt „Sicherheitsdatenblatt“ als Titel; mit {sections} der 16 Abschnitte ist das Dokument eine Sicherheitsinformation, kein Sicherheitsdatenblatt. |
| `leaflet-title` | – | Das Dokument nennt sich „Sicherheitsdatenblatt zum sicheren Umgang mit …“ und nennt die Verordnung (EG) Nr. 1907/2006 nicht: ein Merkblatt zu einem Erzeugnis, kein Sicherheitsdatenblatt. |
| `other-language` | – | Das Dokument ist wie ein Sicherheitsdatenblatt aufgebaut und hat keinen deutschen Titel: ein Sicherheitsdatenblatt in einer anderen Sprache. |
| `cover-only` | – | Das Dokument trägt den Titel eines Sicherheitsdatenblatts und keinen seiner sechzehn Abschnitte: nur ein Deckblatt. |
| `title-in-running-text` | – | Das Dokument nennt ein Sicherheitsdatenblatt nur im Fließtext; keine Zeile trägt es als Titel. |
| `no-safety-data-sheet` | – | Das Dokument hat weder den Titel noch den Aufbau eines Sicherheitsdatenblatts. |
| `not-a-sheet` | – | Die Datei ist kein deutsches Sicherheitsdatenblatt; ihr Inhalt wurde nicht ausgewertet. |
| `unreadable` | – | Der Text der Datei ließ sich nicht lesen; es wurde nichts geprüft. |

## Das Blatt lesen

| Code | Angaben | Satz |
| --- | --- | --- |
| `line-too-long` | `count`, `length` | {count} Zeilen mit mehr als 2.000 Zeichen wurden nicht gelesen, die längste mit {length} Zeichen; ein Blatt druckt keine so langen Zeilen. |
| `no-label-section` | – | Abschnitt 2.2 (Kennzeichnungselemente) wurde nicht gefunden; stattdessen wurde der ganze Abschnitt 2 gelesen. |
| `several-sheets` | `count` | Die Datei enthält {count} Sicherheitsdatenblätter; ihre Kennzeichnungen sind zusammengeführt. |
| `classified-before-clp` | `basis` | Abschnitt 2 stuft nach den Richtlinien vor der CLP-Verordnung ein ({basis}); es wurde keine Kennzeichnung gelesen. |
| `label-before-clp` | – | Die Kennzeichnung (2.2) folgt den Richtlinien vor der CLP-Verordnung: ohne H-, P- und EUH-Code, mit R- oder S-Sätzen, einem Gefahrensymbol oder dem Verweis auf die EG-Richtlinien. |
| `no-hazard-codes` | – | Die Kennzeichnung trägt keinen H-Satz. |
| `label-undetermined` | – | Die Kennzeichnung sagt, die Einstufung sei nicht bestimmt; das Blatt nennt für das Produkt keine Kennzeichnung. |
| `no-precautionary-codes` | – | Die Kennzeichnung trägt keinen P-Satz. |
| `euh-wording-outside-label` | `statement`, `sentence` | {statement} steht nur außerhalb der Kennzeichnung: {sentence} |
| `signal-word-not-taken` | `signal_word` | Das Signalwort „{signal_word}“ wurde nicht übernommen: Abschnitt 2 nennt das Produkt nicht eingestuft, und die Kennzeichnung druckt keinen H-Satz. |
| `pictograms-derived` | `pictograms` | Piktogramme aus den H-Sätzen abgeleitet, das Blatt nennt keine: {pictograms} |
| `precautionary-wording-unclear` | `codes` | Ein Sicherheitshinweis ohne Code passt gleich gut zu {codes}; keiner davon wurde übernommen. |
| `label-line-unassigned` | `line` | Eine Zeile der Kennzeichnung wurde nichts zugeordnet: {line} |
| `statement-too-long` | `codes` | Der Satz {codes} ist nach 100 Zeilen abgeschnitten; was folgt, gehört zu keinem Satz. |
| `no-identification-section` | – | Abschnitt 1 wurde nicht gefunden; der Lieferant lässt sich nicht lesen. |
| `no-supplier-name` | – | In Abschnitt 1 wurde kein Name des Lieferanten gefunden. |
| `no-supplier-address` | – | In Abschnitt 1 wurde keine Anschrift des Lieferanten gefunden. |
| `no-supplier-phone` | – | In Abschnitt 1 wurde keine Telefonnummer des Lieferanten gefunden. |
| `no-emergency-phone` | – | In Abschnitt 1 wurde keine Notrufnummer gefunden. |

## Befunde

| Code | Angaben | Satz |
| --- | --- | --- |
| `wording-deviates` | `statement`, `sheet`, `regulation` | {statement}: Das Blatt druckt „{sheet}“, die Verordnung sagt „{regulation}“. |
| `undated` | – | Das Blatt trägt kein lesbares Überarbeitungs- oder Ausgabedatum. |
| `predates-annex-ii` | `revised` | Überarbeitet am {revised}, vor dem 01.01.2021: Das Blatt kann Anhang II der REACH-Verordnung in der Fassung der Verordnung (EU) 2020/878 nicht erfüllen. |
| `revised-in-future` | `revised`, `today` | Überarbeitet am {revised}, nach dem {today}, dem Tag der Prüfung: Das Datum kann nicht stimmen und zählt nicht für das Alter des Blatts. |
| `classification-undetermined` | – | Die Kennzeichnung sagt, die Einstufung sei nicht bestimmt. |
| `old-classification` | – | Abschnitt 2 stuft nach der Richtlinie 67/548/EWG oder 1999/45/EG ein (R-Sätze, Gefahrensymbole) und trägt keine Kennzeichnung nach der CLP-Verordnung; Gemische sind seit dem 1. Juni 2015 nach der Verordnung (EG) Nr. 1272/2008 einzustufen. |
| `old-format` | `revised` | Überarbeitet am {revised}, aber aufgebaut wie vor der Verordnung (EU) 2020/878: keine endokrinschädlichen Eigenschaften, kein Unterabschnitt 11.2, kein Unterabschnitt 12.7. |
| `classification-not-stated` | – | Abschnitt 2 nennt weder eine Gefahrenklasse noch sagt er, das Produkt sei nicht eingestuft, und die Kennzeichnung trägt weder H-Satz noch Signalwort noch Piktogramm. |
| `classification-contradicts-label` | – | Abschnitt 2 nennt das Produkt nicht eingestuft, und die Kennzeichnung trägt einen H-Satz, ein Signalwort oder ein Piktogramm: Das Blatt widerspricht sich, oder eine der beiden Stellen ist falsch gelesen. |
| `label-not-found` | – | Abschnitt 2 stuft das Produkt ein, und eine Kennzeichnung (2.2) wurde nicht gefunden; Anhang II der REACH-Verordnung verlangt sie dort. |
| `label-without-hazard-statement` | – | Abschnitt 2 stuft das Produkt ein, und in der Kennzeichnung wurde kein H-Satz gefunden; die Einstufung verlangt ihre Gefahrenhinweise auf dem Etikett (CLP Art. 27). |
| `label-without-precautionary-statement` | – | Abschnitt 2 stuft das Produkt ein, und in der Kennzeichnung wurde kein P-Satz gefunden; die Einstufung verlangt die einschlägigen Sicherheitshinweise auf dem Etikett (CLP Art. 22). |
| `hazard-statement-not-in-label` | `statement` | Abschnitt 2.1 nennt {statement} zur Einstufung, und in der Kennzeichnung wurde der Satz nicht gefunden; die Einstufung verlangt ihn auf dem Etikett (CLP Art. 27). |
| `signal-word-not-found` | `expected` | Die Codes der Kennzeichnung verlangen das Signalwort „{expected}“, und es wurde keines gefunden (CLP Art. 20). |
| `different-products` | `products` | Die Datei enthält Sicherheitsdatenblätter verschiedener Produkte: {products} |
| `country-editions-differ` | `fields` | Die Blätter desselben Produkts für verschiedene Länder weichen voneinander ab: {fields} |
| `euh-outside-label` | `statement`, `sentence` | {statement} steht nur außerhalb der Kennzeichnung: {sentence} |
| `not-german` | – | Ein Sicherheitsdatenblatt in einer anderen Sprache: Für den Verkauf in Deutschland muss das Blatt deutsch sein (REACH Art. 31 Abs. 5). |

## Die eingebettete Datei

| Code | Angaben | Satz |
| --- | --- | --- |
| `embedded-too-large` | `limit_bytes` | Die eingebettete Datei ist größer als {limit_bytes} Bytes. |
| `embedded-doctype` | – | Die eingebettete Datei trägt eine Dokumenttyp-Deklaration. |
| `embedded-not-xml` | `detail` | Die eingebettete Datei ist kein wohlgeformtes XML: {detail} |
| `embedded-wrong-root` | `root` | Die eingebettete Datei ist keine eSDScom-Datei: Ihr Wurzelelement ist {root}. |
| `embedded-no-datasheet` | – | Die eingebettete Datei enthält kein Element Datasheet. |

## Ein Sprachmodell fragen

| Code | Angaben | Satz |
| --- | --- | --- |
| `model-http-error` | `status` | Der Endpunkt hat mit HTTP {status} geantwortet. |
| `model-unreachable` | `reason` | Der Endpunkt hat nicht geantwortet: {reason} |
| `model-reply-not-json` | – | Die Antwort des Endpunkts ist kein JSON. |
| `model-reply-without-message` | – | Die Antwort des Endpunkts enthält keine Nachricht. |
| `model-reply-empty` | – | Die Nachricht des Modells ist leer. |
| `model-answer-unreadable` | `detail` | Die Antwort des Modells lässt sich nicht als Antwort lesen: {detail} |
| `model-not-asked` | – | Kein deutsches Sicherheitsdatenblatt: Das Modell wird nicht gefragt. |

## Zeilen auf der Fehlerausgabe

| Code | Angaben | Satz |
| --- | --- | --- |
| `cli-file-failed` | `path`, `reason` | [sdb-reader] FEHLER: {path}: {reason} |
| `cli-file-broke` | `path`, `error` | [sdb-reader] FEHLER: {path}: {error} |
| `cli-no-embedded-file` | `path` | [sdb-reader] {path}: keine eingebettete eSDScom-Datei |
| `cli-embedded-not-handed-out` | `path`, `filename`, `reason` | [sdb-reader] FEHLER: {path}: Die eingebettete Datei „{filename}“ wird nicht herausgegeben. {reason} |
| `cli-saved` | `path`, `target` | [sdb-reader] {path}: gespeichert als {target} |
| `cli-half-line-removed` | `output` | [sdb-reader] {output}: Die letzte Zeile war unvollständig und ist entfernt; ihre Datei wird neu gelesen. |
| `cli-progress` | `done`, `total`, `failed` | [sdb-reader] {done} von {total} Dateien fertig, gescheitert: {failed} |
| `cli-interrupted` | `done`, `total` | [sdb-reader] Abgebrochen nach {done} von {total} Dateien. Mit --output und --resume setzt derselbe Aufruf den Lauf fort. |
| `cli-summary-read` | `files`, `skipped`, `excluded`, `failed` | [sdb-reader] Dateien: {files}; früher erledigt: {skipped}; ausgenommen: {excluded}; gescheitert: {failed} |
| `cli-summary-ask` | `files`, `skipped`, `excluded`, `asked`, `failed`, `prompt_tokens`, `completion_tokens` | [sdb-reader] Dateien: {files}; früher erledigt: {skipped}; ausgenommen: {excluded}; gefragt: {asked}; gescheitert: {failed}; Token gesendet: {prompt_tokens}, empfangen: {completion_tokens} |

## Zwei Läufe vergleichen

| Code | Angaben | Satz |
| --- | --- | --- |
| `diff-run` | `side`, `path`, `kind`, `files` | {side}: {path} ({kind}), Dateien: {files} |
| `diff-files` | `both`, `only_a`, `only_b`, `not_compared` | Dateien in beiden: {both}; nur in A: {only_a}; nur in B: {only_b}; nicht vergleichbar: {not_compared} |
| `diff-differing` | `differing`, `counted_only` | Dateien mit Abweichung: {differing}; nur gezählt: {counted_only} |
| `diff-none` | – | Keine Abweichung. |
| `diff-field` | `field`, `gained`, `lost`, `changed` | {field}: dazugekommen {gained}, weggefallen {lost}, geändert {changed} |
| `diff-field-counted-only` | `field`, `gained`, `lost`, `changed` | {field}, nur gezählt: dazugekommen {gained}, weggefallen {lost}, geändert {changed} |
| `diff-stages-differ` | `a`, `b` | [sdb-reader] WARNUNG: Die Läufe stammen aus verschiedenen Lese-Stufen (A: {a}; B: {b}): Abweichungen können vom Text der PDF-Dateien kommen statt vom Lesen. |
| `diff-models-differ` | `a`, `b` | [sdb-reader] WARNUNG: Die Läufe haben verschiedene Modelle gefragt (A: {a}; B: {b}). |
| `diff-questions-differ` | `a`, `b` | [sdb-reader] WARNUNG: Die Läufe haben nicht dieselbe Frage gestellt (A: {a}; B: {b}): Die Antworten gelten verschiedenen Fragen. |

## Der Bericht von show

| Code | Angaben | Satz |
| --- | --- | --- |
| `show-kind-sheet` | `sheets` | Sicherheitsdatenblatt, deutsch, 1 Blatt / Sicherheitsdatenblatt, deutsch, {sheets} Blätter |
| `show-kind-other-language` | – | Sicherheitsdatenblatt in einer anderen Sprache |
| `show-kind-safety-information` | – | Sicherheitsinformation, kein Sicherheitsdatenblatt |
| `show-kind-document` | – | Kein Sicherheitsdatenblatt |
| `show-kind-unreadable` | – | Nicht lesbar |
| `show-kind-broke` | – | Beim Lesen ist ein Fehler aufgetreten; Näheres steht in der Fehlerausgabe. |
| `show-cover-page` | – | Vor den Blättern steht ein Deckblatt; es wird nicht gelesen. |
| `show-cover-page-display` | `term` | Vor den Blättern steht ein Deckblatt; es nennt ein Display: „{term}“. |
| `show-line-cover-page` | – | mit Deckblatt |
| `show-line-cover-page-display` | `term` | mit Deckblatt (Display: „{term}“) |
| `show-sheet-of` | `number`, `count` | Blatt {number} von {count} |
| `show-whole-file` | – | Die Datei als Ganzes |
| `show-oldest-revised` | `number`, `date` | Ältestes Blatt: Blatt {number}, überarbeitet am {date} |
| `show-oldest-issued` | `number`, `date` | Ältestes Blatt: Blatt {number}, ausgegeben am {date} |
| `show-oldest-none` | – | Ältestes Blatt: keines trägt ein Datum |
| `show-label-product` | – | Produkt |
| `show-label-supplier` | – | Lieferant |
| `show-label-contact` | – | Kontakt |
| `show-label-emergency` | – | Notruf |
| `show-label-revised` | – | Überarbeitet |
| `show-label-issued` | – | Ausgegeben |
| `show-label-labelling` | – | Kennzeichnung |
| `show-label-notes` | – | Hinweise |
| `show-date` | `date` | {date} |
| `show-information-email` | `email` | Auskunft: {email} |
| `show-product-dated` | `product`, `dated` | {product} ({dated}) |
| `show-with-version` | `value`, `version` | {value} (Version {version}) |
| `show-not-stated` | – | nicht genannt |
| `show-no-labelling` | – | keine |
| `show-no-signal-word` | – | kein Signalwort |
| `show-no-pictograms` | – | keine Piktogramme |
| `show-no-statements` | – | keine H-, P- oder EUH-Sätze |
| `show-needs-sheet` | – | Braucht ein Sicherheitsdatenblatt: ja |
| `show-needs-no-sheet` | – | Braucht ein Sicherheitsdatenblatt: nein |
| `show-stated-voluntary` | – | Das Blatt nennt sich freiwillig ausgestellt oder nicht vorgeschrieben. |
| `show-stated-article` | – | Das Blatt nennt sein Produkt ein Erzeugnis. |
| `show-no-notes` | – | keine |
| `show-no-product` | – | Produkt nicht genannt |
| `show-undated` | – | ohne Datum |
| `show-notes` | `notes` | 1 Hinweis / {notes} Hinweise |
| `show-summary` | `files`, `sheets`, `others`, `failed`, `with_notes`, `excluded` | Dateien: {files}; Sicherheitsdatenblätter: {sheets}; andere Dokumente: {others}; nicht lesbar: {failed}; mit Hinweisen: {with_notes}; ausgenommen: {excluded} |
| `show-interrupted` | `done`, `total` | [sdb-reader] Abgebrochen nach {done} von {total} Dateien. |

## Aus aufbewahrten Texten früherer Fassungen

| Code | Angaben | Satz |
| --- | --- | --- |
| `unknown` | `text` | {text} |
