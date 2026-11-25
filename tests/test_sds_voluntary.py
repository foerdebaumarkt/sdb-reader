"""A sheet that calls itself voluntary needs none for its product (SDB-142).

The sheets are invented; each sentence is a form sheets print.
"""

from __future__ import annotations

from datetime import date

import pytest

from sdb_reader import read_extraction, reading_to_dict
from sdb_reader.compliance import SheetDuty, sheet_duty, sheet_findings
from sdb_reader.extraction import ExtractionResult
from sdb_reader.parser import (
    ParsedSheet,
    SDSParser,
    says_article,
    says_voluntary,
)
from sdb_reader.schema import HazardStatements, SafetyDataSheet, StatedClassification

TITLE = "Sicherheitsdatenblatt\ngemäß Verordnung (EG) Nr. 1907/2006\n"
SECTION_1 = (
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs und des Unternehmens\n"
    "1.1 Produktidentifikator\nHandelsname: Musterbatterie\n"
    "{note}"
    "1.3 Einzelheiten zum Lieferanten\nMuster GmbH\nBeispielweg 1\n12345 Musterstadt\n"
)
LABELLED = (
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Einstufung gemäß Verordnung (EG) Nr. 1272/2008\n"
    "Skin Corr. 1A\nH314\nVerursacht schwere Verätzungen der Haut und schwere "
    "Augenschäden.\n"
    "2.2 Kennzeichnungselemente\n"
    "Signalwort: Gefahr\n"
    "Gefahrenhinweise\n"
    "H314 Verursacht schwere Verätzungen der Haut und schwere Augenschäden.\n"
    "Sicherheitshinweise\n"
    "P280 Schutzhandschuhe/Schutzkleidung/Augenschutz/Gesichtsschutz tragen.\n"
    "{label_end}"
    "2.3 Sonstige Gefahren\nKeine.\n"
)
UNLABELLED = (
    "ABSCHNITT 2: Mögliche Gefahren\n"
    "2.1 Einstufung des Stoffs oder Gemischs\n"
    "Das Gemisch ist nicht als gefährlich eingestuft im Sinne der Verordnung "
    "(EG) Nr. 1272/2008.\n"
    "2.2 Kennzeichnungselemente\n"
    "{label}"
    "2.3 Sonstige Gefahren\nKeine.\n"
)
REST = (
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen\nGemisch.\n"
    "ABSCHNITT 4: Erste-Hilfe-Maßnahmen\nKeine besonderen Maßnahmen.\n"
    "{end}"
)
ARTICLE = (
    "Anmerkung: Dieses Produkt ist ein Erzeugnis und daher ist die Erstellung "
    "eines\nSicherheitsdatenblattes (SDS) gesetzlich nicht verpflichtend. Dieses "
    "auf freiwilliger Basis\nerstellte SDS beinhaltet Informationen zum sicheren "
    "Umgang.\n"
)
ON_REQUEST = "Sicherheitsdatenblatt auf Anfrage erhältlich."


def _parse(text: str) -> ParsedSheet:
    return SDSParser().parse(
        ExtractionResult(
            text=text,
            raw_text=text,
            extractor="unit-test",
            pages_sampled=1,
            warnings=[],
            metadata={},
        )
    )


def _sheet(
    *, note: str = "", section_2: str = LABELLED, label_end: str = "", end: str = ""
) -> str:
    return (
        TITLE
        + SECTION_1.format(note=note)
        + section_2.format(label_end=label_end, label=label_end)
        + REST.format(end=end)
    )


def _required(result: ParsedSheet) -> bool:
    return sheet_duty(result.sheet) is SheetDuty.REQUIRED


def _stating(
    label: dict[str, object] | None = None,
    stated: str | None = None,
    *,
    voluntary: bool = False,
    article: bool = False,
) -> SafetyDataSheet:
    """A sheet with this label that states this about its product."""
    return SafetyDataSheet(
        None,
        None,
        None,
        None,
        "de",
        hazard_statements=HazardStatements(**(label or {})),
        stated_classification=StatedClassification(stated or "not-stated"),
        stated_voluntary=voluntary,
        stated_article=article,
    )


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize(
    "sentence",
    [
        "Für dieses Produkt ist gemäß Artikel 31 der REACH-Verordnung kein "
        "Sicherheitsdatenblatt erforderlich.",
        "Für das Produkt ist somit nach REACH Artikel 2, 7b) kein "
        "Sicherheitsdatenblatt erforderlich.",
        "Für diesen Stoff/dieses Gemisch ist nach Artikel 31(1) der VO (EG) "
        "1907/2006 kein Sicherheitsdatenblatt zu erstellen.",
        "Dieses Produkt ist ein Erzeugnis und daher ist die Erstellung eines "
        "Sicherheitsdatenblattes (SDS) gesetzlich nicht verpflichtend.",
        "Das Bereitstellen eines Sicherheitsdatenblattes ist nach Art. 31 der "
        "Verordnung 1907/2006 (REACH) für Erzeugnisse nicht vorgeschrieben und "
        "erfolgt auf freiwilliger Basis.",
        "Die Erstellung eines Sicherheitsdatenblattes ist gem. Artikel 31 "
        "REACH-Verordnung für Erzeugnisse nicht vorgeschrieben.",
        "Das SDB ist für dieses Produkt rechtlich nicht vorgeschrieben.",
        "Platten fallen nicht unter die REACH-Verordnung, womit "
        "Sicherheitsdatenblätter gesetzlich nicht erforderlich sind.",
        "Aus den genannten Gründen sind wir nicht verpflichtet, ein "
        "Sicherheitsdatenblatt zu erstellen und herauszugeben.",
        "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt: es ist nach "
        "Artikel 31 der Verordnung (EG) Nr. 1907/2006 nicht erforderlich.",
        "Dieses Produktsicherheitsdatenblatt wurde auf freiwilliger Basis erstellt.",
        "Dieses auf freiwilliger Basis erstellte SDS beinhaltet Informationen "
        "zum sicheren Umgang.",
        "Die Bereitstellung von Informationen im Format eines "
        "Sicherheitsdatenblattes erfolgt auf freiwilliger Basis.",
        "Da Erzeugnisse nicht unter Artikel 31 fallen, erfolgt die Erstellung "
        "dieses Sicherheitsdatenblatts auf freiwilliger Basis.",
        "Freiwillige Produktinformation in Anlehnung an das "
        "Sicherheitsdatenblatt-Format",
        "Freiwillige Sicherheitsinformation in Anlehnung an das "
        "Sicherheitsdatenblattformat gemäß Verordnung (EG) Nr. 1907/2006",
        "Diese Unterlage ist eine freiwillige Information und kein "
        "Sicherheitsdatenblatt nach CLP.",
    ],
)
def test_a_sheet_says_it_is_voluntary_or_not_prescribed(sentence: str) -> None:
    assert says_voluntary(sentence)
    # Also broken across lines, as a narrow column prints it.
    assert says_voluntary(sentence.replace(" ", "\n"))


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize(
    "text",
    [
        # The word alone, in the boilerplate on Annex XVII.
        "Beschränkung der Herstellung, des Inverkehrbringens und der Verwendung "
        "bestimmter gefährlicher Stoffe, Mischungen und Erzeugnisse: Nicht anwendbar.",
        "Handelsname: Musterpaste\nSDB-Gruppe: 12345\nUFI: nicht notwendig",
        "vPvB: nicht relevant – keine Registrierung erforderlich",
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006\n"
        "Signalwort: Nicht erforderlich\nPiktogramme: Nicht erforderlich",
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006 Seite 3/9\n"
        "Atemschutz nicht erforderlich",
        # A remark on an ingredient named voluntarily, then the page header.
        "Anmerkung [4] Freiwillige Information\nSeite 1(9)\n"
        "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006",
        "Das Gemisch ist nicht eingestuft. Es wird jedoch ein Sicherheitsdatenblatt "
        "auf Anfrage zur Verfügung gestellt.",
        "Betriebsanweisung oder Sicherheitsdatenblatt vorzeigen. Erbrechen ist "
        "nicht erforderlich.",
    ],
)
def test_other_words_do_not_say_it(text: str) -> None:
    assert not says_voluntary(text)


@pytest.mark.spec("SDB-142")
def test_the_label_stays_as_printed_and_no_sheet_is_needed() -> None:
    result = _parse(_sheet(note=ARTICLE))
    sheet = result.sheet

    assert sheet.stated_voluntary is True
    assert sheet.stated_article is True
    # What the sheet prints, the reading names.
    assert sheet.hazard_statements.hazard_codes == ["H314"]
    assert sheet.hazard_statements.signal_word == "Gefahr"
    assert sheet.stated_classification is StatedClassification.CLASSIFIED
    assert _required(result) is False


@pytest.mark.spec("SDB-142")
def test_without_the_sentence_the_same_sheet_is_needed() -> None:
    result = _parse(_sheet())

    assert result.sheet.stated_voluntary is False
    assert _required(result) is True


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize("where", ["title", "section-16"])
def test_the_sentence_counts_wherever_it_stands(where: str) -> None:
    sentence = (
        "Für dieses Produkt ist gemäß Artikel 31 der REACH-Verordnung kein "
        "Sicherheitsdatenblatt erforderlich.\n"
    )
    label = "Gefahrenpiktogramme: GHS07\n"
    plain = _sheet(section_2=UNLABELLED, label_end=label)
    text = (
        _sheet(
            section_2=UNLABELLED,
            label_end=label,
            end="ABSCHNITT 16: Sonstige Angaben\n" + sentence,
        )
        if where == "section-16"
        else plain.replace(TITLE, TITLE + sentence, 1)
    )

    result = _parse(text)

    assert _required(_parse(plain)) is True
    assert result.sheet.stated_voluntary is True
    assert result.sheet.stated_article is False
    assert _required(result) is False


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize(
    "sentence",
    [
        "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt: es ist nach "
        "Artikel 31 der Verordnung (EG) Nr. 1907/2006 nicht erforderlich.\n",
        "Freiwillige Sicherheitsinformation in Anlehnung an das "
        "Sicherheitsdatenblattformat gemäß Verordnung (EG) Nr. 1907/2006\n",
    ],
)
def test_a_classified_mixture_needs_its_sheet_whatever_the_sheet_calls_itself(
    sentence: str,
) -> None:
    # Due to a distributor or downstream user who asks (REACH Art. 31(4)).
    result = _parse(_sheet(note=sentence))
    sheet = result.sheet

    assert sheet.stated_voluntary is True
    assert sheet.stated_article is False
    assert sheet.hazard_statements.hazard_codes == ["H314"]
    assert _required(result) is True
    # By the label alone as well, where section 2 is not read as classifying.
    assert (
        sheet_duty(_stating({"hazard_codes": ["H314"]}, voluntary=True))
        is SheetDuty.REQUIRED
    )
    assert (
        sheet_duty(_stating(stated="classified", voluntary=True)) is SheetDuty.REQUIRED
    )


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize(
    ("text", "article"),
    [
        (
            "Dieses Produkt ist ein Erzeugnis und daher ist die Erstellung eines "
            "Sicherheitsdatenblattes gesetzlich nicht verpflichtend.",
            True,
        ),
        (
            "Freiwillige Produktinformation in Anlehnung an das "
            "Sicherheitsdatenblatt-Format\nDie Kartuschen gelten gemäß Artikel 3 "
            "der Verordnung als Erzeugnis.",
            True,
        ),
        (
            "Das Bereitstellen eines Sicherheitsdatenblattes ist nach Art. 31 der "
            "Verordnung für Erzeugnisse nicht vorgeschrieben.",
            True,
        ),
        # The regulation's row stands in every sheet and names no product.
        (
            "Beschränkung der Herstellung, des Inverkehrbringens und der "
            "Verwendung bestimmter gefährlicher Stoffe, Gemische und Erzeugnisse: "
            "Nicht anwendbar.\nFür dieses Produkt ist gemäß Artikel 31 der "
            "REACH-Verordnung kein Sicherheitsdatenblatt erforderlich.",
            False,
        ),
        # The word far from the sentence says nothing about it.
        (
            "Das Erzeugnis wird in Kartons geliefert.\n"
            + "Keine besonderen Maßnahmen erforderlich.\n" * 12
            + "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt.",
            False,
        ),
        # Without the sentence there is nothing the word stands beside.
        ("Dieses Produkt ist ein Erzeugnis.", False),
    ],
)
def test_the_sheet_calls_its_product_an_article_beside_the_sentence(
    text: str, article: bool
) -> None:
    assert says_article(text) is article


@pytest.mark.spec("SDB-142")
@pytest.mark.parametrize(
    "label",
    [
        "Ergänzende Gefahrenmerkmale\nEUH210 " + ON_REQUEST + "\n",
        # Without its code, as a label by the old directives prints it.
        "Zusätze:\nSicherheitsdatenblatt auf Anfrage für berufsmäßige Verwender "
        "erhältlich.\n",
    ],
)
def test_a_label_that_offers_the_sheet_on_request_goes_first(label: str) -> None:
    voluntary = (
        "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt: es ist nach "
        "Artikel 31 der Verordnung (EG) Nr. 1907/2006 nicht erforderlich.\n"
    )
    result = _parse(_sheet(note=voluntary, section_2=UNLABELLED, label_end=label))

    assert result.sheet.stated_voluntary is True
    assert _required(result) is True


@pytest.mark.spec("SDB-220")
@pytest.mark.parametrize(
    ("code", "sentence"),
    [
        ("EUH208", "Enthält Musterstoff."),
        ("EUH204", "Enthält Isocyanate."),
        ("EUH205", "Enthält epoxidhaltige Verbindungen."),
    ],
)
def test_a_sensitising_substance_owes_the_sheet_even_on_a_voluntary_one(
    code: str, sentence: str
) -> None:
    label = f"{code} {sentence} Kann allergische Reaktionen hervorrufen.\n"
    voluntary = "Dieses Sicherheitsdatenblatt wurde freiwillig erstellt.\n"

    with_word = _parse(_sheet(note=voluntary, section_2=UNLABELLED, label_end=label))
    without = _parse(_sheet(section_2=UNLABELLED, label_end=label))

    assert with_word.sheet.hazard_statements.supplemental_codes == [code]
    assert _required(with_word) is True
    assert _required(without) is True


@pytest.mark.spec("SDB-220")
@pytest.mark.parametrize(
    "label",
    [
        "EUH066 Wiederholter Kontakt kann zu spröder oder rissiger Haut führen.\n",
        "EUH401 Zur Vermeidung von Risiken für Mensch und Umwelt die "
        "Gebrauchsanleitung einhalten.\n",
    ],
)
def test_another_supplemental_statement_owes_no_sheet(label: str) -> None:
    result = _parse(_sheet(section_2=UNLABELLED, label_end=label))

    assert result.sheet.hazard_statements.supplemental_codes
    assert _required(result) is False


@pytest.mark.spec("SDB-142")
def test_the_record_says_both() -> None:
    text = _sheet(note=ARTICLE)
    reading = read_extraction(
        ExtractionResult(
            text=text,
            raw_text=text,
            extractor="unit-test",
            pages_sampled=1,
            warnings=[],
            metadata={},
        )
    )

    record = reading_to_dict(reading)

    # The kind stays (SDB-66): the file calls itself a safety data sheet.
    assert record["verification"]["kind"] == "safety-data-sheet"
    assert record["sheet"]["stated_voluntary"] is True
    assert record["sheet"]["stated_article"] is True
    assert record["sheet"]["sheet_duty"] == "not-required"
    assert record["sheet"]["hazard_statements"]["hazard_codes"] == ["H314"]


@pytest.mark.spec("SDB-142")
def test_the_old_format_is_not_held_against_a_voluntary_sheet() -> None:
    dated = TITLE + "Überarbeitet am: 01.03.2023\n"
    sections = (
        "ABSCHNITT 11: Toxikologische Angaben\nKeine Daten.\n"
        "ABSCHNITT 12: Umweltbezogene Angaben\nKeine Daten.\n"
    )
    needed = _parse(_sheet(end=sections).replace(TITLE, dated, 1))
    voluntary = _parse(_sheet(note=ARTICLE, end=sections).replace(TITLE, dated, 1))
    day = date(2026, 1, 1)

    def codes(result: ParsedSheet) -> set[str]:
        return {
            finding.code
            for finding in sheet_findings(result.sheet, result.warnings, today=day)
        }

    assert "old-format" in codes(needed)
    assert "old-format" not in codes(voluntary)


@pytest.mark.spec("SDB-142")
def test_a_file_is_voluntary_where_each_of_its_sheets_says_so() -> None:
    first = _sheet(note=ARTICLE)
    second = _sheet().replace("Musterbatterie", "Musterreiniger")

    mixed = _parse(first + second)
    both = _parse(first + first.replace("Musterbatterie", "Musterbatterie 2"))

    assert len(mixed.parts) == 2
    assert [part.sheet.stated_voluntary for part in mixed.parts] == [True, False]
    assert mixed.sheet.stated_voluntary is False
    assert _required(mixed) is True
    assert both.sheet.stated_voluntary is True
    assert _required(both) is False


ARTICLE_UNLABELLED = (
    "Dieses Produkt ist ein Erzeugnis, deshalb ist es nach EG-Richtlinien "
    "[REACH/CLP]/GefStoffV\nnicht kennzeichnungspflichtig.\n"
)


@pytest.mark.spec("SDB-154")
@pytest.mark.parametrize(
    "sentence",
    [
        ARTICLE_UNLABELLED,
        "Gemäß REACH, Artikel 3 (3) stellt dieses Produkt / stellen diese "
        "Produkte ein Erzeugnis dar. Ein Erzeugnis unterliegt nicht der "
        "gefahrstoffrechtlichen Kennzeichnungspflicht.",
        "Das Produkt gilt nach Artikel 3 der Verordnung (EG) 1907/2006 (REACH) "
        "als Erzeugnis und ist nicht kennzeichnungspflichtig gemäß: - Art. 4, "
        "Verordnung 1272/2008 (CLP)",
        "Das Produkt ist ein Erzeugnis im Sinne des Artikels 3 Nr. 3 der "
        "REACH-Verordnung und somit nicht kennzeichnungspflichtig gemäß "
        "CLP-Verordnung.",
        "Dieses Produkt unterliegt als Erzeugnis nicht der Verordnung (EG) Nr. "
        "1272/2008 [CLP] und ist nicht kennzeichnungspflichtig im Sinne dieser "
        "Verordnung.",
        "Es handelt sich um ein Erzeugnis. Das Produkt ist nicht "
        "kennzeichnungspflichtig.",
    ],
)
def test_a_sheet_says_its_product_is_an_article_and_needs_no_labelling(
    sentence: str,
) -> None:
    assert says_article(sentence)
    assert says_article(sentence.replace(" ", "\n"))
    assert not says_voluntary(sentence)


@pytest.mark.spec("SDB-154")
@pytest.mark.parametrize(
    "text",
    [
        # The bare word: it does not say the product is one.
        "Das Erzeugnis ist nach EG-Richtlinien nicht kennzeichnungspflichtig.",
        "Das Produkt ist kein Erzeugnis. Es ist nicht kennzeichnungspflichtig.",
        # An article, and nothing about labelling.
        "Bei dem Produkt handelt es sich um ein Erzeugnis.",
        # The regulation's row.
        "Stoffe, Gemische und Erzeugnisse: Das Gemisch ist nicht "
        "kennzeichnungspflichtig.",
        # Too far apart to belong together.
        "Das Produkt ist ein Erzeugnis. " + "Keine Angaben. " * 20 + "Das Gemisch "
        "ist nicht kennzeichnungspflichtig.",
    ],
)
def test_other_words_name_no_article(text: str) -> None:
    assert not says_article(text)


@pytest.mark.spec("SDB-154")
def test_an_article_needs_no_sheet_though_the_sheet_does_not_call_itself_voluntary() -> (
    None
):
    result = _parse(_sheet(label_end=ARTICLE_UNLABELLED))
    sheet = result.sheet

    assert sheet.stated_voluntary is False
    assert sheet.stated_article is True
    # What the sheet prints, the reading names.
    assert sheet.hazard_statements.hazard_codes == ["H314"]
    assert sheet.stated_classification is StatedClassification.CLASSIFIED
    assert _required(result) is False
    assert (
        sheet_duty(_stating(stated="classified", article=True))
        is SheetDuty.NOT_REQUIRED
    )


@pytest.mark.spec("SDB-154")
def test_a_label_that_offers_the_sheet_on_request_goes_first_for_an_article() -> None:
    result = _parse(_sheet(label_end=ARTICLE_UNLABELLED + ON_REQUEST + "\n"))

    assert result.sheet.stated_article is True
    assert _required(result) is True
    assert (
        sheet_duty(_stating({"supplemental_codes": ["EUH210"]}, article=True))
        is SheetDuty.REQUIRED
    )


@pytest.mark.spec("SDB-154")
def test_the_old_format_is_not_held_against_such_an_article() -> None:
    dated = TITLE + "Überarbeitet am: 01.03.2023\n"
    sections = (
        "ABSCHNITT 11: Toxikologische Angaben\nKeine Daten.\n"
        "ABSCHNITT 12: Umweltbezogene Angaben\nKeine Daten.\n"
    )
    needed = _parse(_sheet(end=sections).replace(TITLE, dated, 1))
    article = _parse(
        _sheet(label_end=ARTICLE_UNLABELLED, end=sections).replace(TITLE, dated, 1)
    )
    day = date(2026, 1, 1)

    def codes(result: ParsedSheet) -> set[str]:
        return {
            finding.code
            for finding in sheet_findings(result.sheet, result.warnings, today=day)
        }

    assert "old-format" in codes(needed)
    assert "old-format" not in codes(article)
