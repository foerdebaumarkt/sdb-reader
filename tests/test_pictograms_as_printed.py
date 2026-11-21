"""The pictograms as the label prints them, and the ones its codes call for
(SDB-179 to SDB-181, SDW-47, BIB-25).

Every sheet here is drawn for the test and its text invented; the pictograms
are the public-domain drawings the references are made from.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from sdb_reader import (
    HazardStatements,
    LabelImages,
    LabelImagesStatus,
    clp_expected,
    extraction_from_dict,
    label_images_from_dict,
    label_images_stage,
    label_images_to_dict,
    read_extraction,
    read_label_images,
    read_sheet,
    sheet_findings,
    sheet_from_dict,
    sheet_to_dict,
)
from sdb_reader.extraction import ExtractionResult
from sdb_reader.messages import Message
from sdb_reader.parser import ParsedSheet, states_no_pictograms

DRAWINGS = Path(__file__).parent.parent / "tools" / "pictograms" / "drawings"

_HEAD = [
    "Sicherheitsdatenblatt gemäß Verordnung (EG) Nr. 1907/2006",
    "ABSCHNITT 1: Bezeichnung des Stoffs bzw. des Gemischs",
    "Handelsname: Musterlack",
    "Überarbeitet am: 02.09.2024",
    "ABSCHNITT 2: Mögliche Gefahren",
    "2.1 Einstufung des Stoffs oder Gemischs",
    "Flam. Liq. 2, H225; Eye Irrit. 2, H319",
    "2.2 Kennzeichnungselemente",
    "Gefahrenpiktogramme",
]
_TAIL = [
    "Signalwort: Gefahr",
    "H225 Flüssigkeit und Dampf leicht entzündbar.",
    "H319 Verursacht schwere Augenreizung.",
    "P210 Von Hitze fernhalten. Nicht rauchen.",
    "2.3 Sonstige Gefahren",
    "Keine.",
    "ABSCHNITT 3: Zusammensetzung/Angaben zu Bestandteilen",
]


def _sheet(
    path: Path,
    pictograms: list[str],
    *,
    head: list[str] | None = None,
    tail: list[str] | None = None,
    side: float = 50,
    gap: float = 10,
    elsewhere: tuple[str, ...] = (),
) -> Path:
    """A one-page sheet whose label shows *pictograms* as drawings in a row
    below its heading; *elsewhere* are drawn in section 3, outside it."""
    lines = head if head is not None else _HEAD
    rest = tail if tail is not None else _TAIL
    with pymupdf.open() as document:
        page = document.new_page(width=595, height=842)
        y = 60.0
        for line in lines:
            page.insert_text((50, y), line, fontsize=9)
            y += 14
        x = 60.0
        for code in pictograms:
            _draw(page, code, pymupdf.Rect(x, y, x + side, y + side))
            x += side + gap
        y += side + 18
        for line in rest:
            page.insert_text((50, y), line, fontsize=9)
            y += 14
        x = 60.0
        for code in elsewhere:
            _draw(page, code, pymupdf.Rect(x, y + 10, x + side, y + 10 + side))
            x += side + gap
        document.save(path)
    return path


def _pages(path: Path, *pages: list[str | list[str]], side: float = 50) -> Path:
    """A file of *pages*, each drawn from the top down: a string is a line of
    text, a list a row of pictograms."""
    with pymupdf.open() as document:
        for items in pages:
            page = document.new_page(width=595, height=842)
            y = 60.0
            for item in items:
                if isinstance(item, str):
                    page.insert_text((50, y), item, fontsize=9)
                    y += 14
                    continue
                for n, code in enumerate(item):
                    x = 60.0 + n * (side + 10)
                    _draw(page, code, pymupdf.Rect(x, y, x + side, y + side))
                y += side + 18
        document.save(path)
    return path


def _draw(page: pymupdf.Page, code: str, rect: pymupdf.Rect) -> None:
    with pymupdf.open(DRAWINGS / f"{code}.svg") as drawing:
        as_pdf = pymupdf.open("pdf", drawing.convert_to_pdf())
    with as_pdf:
        page.show_pdf_page(rect, as_pdf, 0)


def _parsed(path: Path) -> ParsedSheet:
    result = read_sheet(path).parser_result
    assert result is not None
    return result


def _findings(parsed: ParsedSheet) -> list[tuple[str, dict[str, str]]]:
    return [
        (finding.code, dict(finding.params))
        for finding in sheet_findings(parsed.sheet, parsed.warnings)
        if finding.code.startswith("pictogram")
    ]


@pytest.mark.spec("SDB-179")
@pytest.mark.parametrize("code", [f"GHS0{n}" for n in range(1, 10)])
def test_each_pictogram_drawn_in_the_label_is_recognised(
    tmp_path: Path, code: str
) -> None:
    images = read_label_images(_sheet(tmp_path / "sheet.pdf", [code]))

    assert images.status is LabelImagesStatus.READ
    assert images.labels == [[code]]
    assert images.unrecognised == [0]


@pytest.mark.spec("SDB-179")
@pytest.mark.parametrize("side", [30, 80])
def test_small_and_large_pictograms_are_recognised(tmp_path: Path, side: float) -> None:
    images = read_label_images(
        _sheet(tmp_path / "sheet.pdf", ["GHS02", "GHS07"], side=side)
    )

    assert images.labels == [["GHS02", "GHS07"]]


@pytest.mark.spec("SDB-179")
def test_pictograms_whose_corners_touch_are_told_apart(tmp_path: Path) -> None:
    images = read_label_images(
        _sheet(tmp_path / "sheet.pdf", ["GHS05", "GHS07", "GHS09"], gap=0)
    )

    assert images.labels == [["GHS05", "GHS07", "GHS09"]]


@pytest.mark.spec("SDB-179")
def test_a_diamond_outside_the_label_does_not_count(tmp_path: Path) -> None:
    images = read_label_images(
        _sheet(tmp_path / "sheet.pdf", ["GHS02"], elsewhere=["GHS06"])
    )

    assert images.labels == [["GHS02"]]


@pytest.mark.spec("SDB-179")
def test_a_red_square_is_no_pictogram(tmp_path: Path) -> None:
    path = _sheet(tmp_path / "sheet.pdf", [])
    with pymupdf.open(path) as document:
        page = document[0]
        top = 60 + 14 * len(_HEAD)
        page.draw_rect(pymupdf.Rect(60, top, 110, top + 50), color=(1, 0, 0), width=4)
        document.saveIncr()

    images = read_label_images(path)

    assert images.labels == [[]]
    assert images.unrecognised == [0]


@pytest.mark.spec("SDB-179")
def test_a_red_diamond_with_no_pictogram_in_it_is_counted_not_named(
    tmp_path: Path,
) -> None:
    path = _sheet(tmp_path / "sheet.pdf", [])
    with pymupdf.open(path) as document:
        page = document[0]
        top = 60 + 14 * len(_HEAD)
        corners = [(85, top), (110, top + 25), (85, top + 50), (60, top + 25)]
        page.draw_polyline([*corners, corners[0]], color=(1, 0, 0), width=4)
        document.saveIncr()

    images = read_label_images(path)

    assert images.labels == [[]]
    assert images.unrecognised == [1]


@pytest.mark.spec("SDB-179")
def test_a_pdf_without_a_text_layer_is_not_looked_at(tmp_path: Path) -> None:
    drawn = _sheet(tmp_path / "drawn.pdf", ["GHS07"])
    scanned = tmp_path / "scanned.pdf"
    with pymupdf.open(drawn) as document, pymupdf.open() as copy:
        picture = document[0].get_pixmap(dpi=72)
        page = copy.new_page(width=595, height=842)
        page.insert_image(page.rect, pixmap=picture)
        copy.save(scanned)

    images = read_label_images(scanned)

    assert images.status is LabelImagesStatus.NO_TEXT_LAYER
    assert images.labels == []


@pytest.mark.spec("SDB-179")
def test_a_page_without_a_label_heading_has_no_label(tmp_path: Path) -> None:
    head = [line for line in _HEAD if "Kennzeichnungselemente" not in line]

    images = read_label_images(_sheet(tmp_path / "sheet.pdf", ["GHS07"], head=head))

    assert images.status is LabelImagesStatus.NO_LABEL


@pytest.mark.spec("SDB-179")
def test_the_reading_has_the_pictograms_the_label_shows(tmp_path: Path) -> None:
    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS02", "GHS07"]))

    label = parsed.sheet.hazard_statements
    assert label.pictograms == ["GHS02", "GHS07"]
    assert clp_expected(label).pictograms == ["GHS02", "GHS07"]
    assert label.drawing_read
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-179")
def test_codes_the_text_names_and_drawings_the_label_shows_are_united(
    tmp_path: Path,
) -> None:
    head = [*_HEAD[:-1], "Gefahrenpiktogramme: GHS07"]

    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS02"], head=head))

    assert parsed.sheet.hazard_statements.pictograms == ["GHS02", "GHS07"]


@pytest.mark.spec("SDB-179")
@pytest.mark.spec("SDB-181")
@pytest.mark.spec("BIB-25")
def test_a_pictogram_the_codes_call_for_and_the_label_lacks_is_a_finding(
    tmp_path: Path,
) -> None:
    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS02"]))

    label = parsed.sheet.hazard_statements
    assert label.pictograms == ["GHS02"]
    assert clp_expected(label).pictograms == ["GHS02", "GHS07"]
    assert _findings(parsed) == [("pictogram-not-found", {"pictogram": "GHS07"})]


@pytest.mark.spec("SDB-181")
def test_a_pictogram_no_code_calls_for_is_a_finding(tmp_path: Path) -> None:
    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS02", "GHS07", "GHS09"]))

    assert parsed.sheet.hazard_statements.pictograms == ["GHS02", "GHS07", "GHS09"]
    assert _findings(parsed) == [("pictogram-not-expected", {"pictogram": "GHS09"})]


@pytest.mark.spec("SDB-179")
@pytest.mark.spec("SDB-181")
def test_a_pictogram_article_26_leaves_out_stays_and_is_a_finding(
    tmp_path: Path,
) -> None:
    head = [*_HEAD[:6], "Eye Dam. 1, H318; Skin Irrit. 2, H315", *_HEAD[7:]]
    tail = [
        "Signalwort: Gefahr",
        "H315 Verursacht Hautreizungen.",
        "H318 Verursacht schwere Augenschäden.",
        "P280 Schutzhandschuhe tragen.",
        *_TAIL[-3:],
    ]

    parsed = _parsed(
        _sheet(tmp_path / "sheet.pdf", ["GHS05", "GHS07"], head=head, tail=tail)
    )

    label = parsed.sheet.hazard_statements
    assert label.pictograms == ["GHS05", "GHS07"]
    assert clp_expected(label).pictograms == ["GHS05"]
    assert _findings(parsed) == [
        ("pictogram-precedence", {"pictogram": "GHS07", "beside": "GHS05"})
    ]


@pytest.mark.spec("SDB-179")
@pytest.mark.spec("SDB-181")
def test_an_unrecognised_diamond_keeps_back_the_finding_of_a_missing_one(
    tmp_path: Path,
) -> None:
    path = _sheet(tmp_path / "sheet.pdf", ["GHS02"])
    with pymupdf.open(path) as document:
        page = document[0]
        top = 60 + 14 * len(_HEAD)
        corners = [(145, top), (170, top + 25), (145, top + 50), (120, top + 25)]
        page.draw_polyline([*corners, corners[0]], color=(1, 0, 0), width=4)
        document.saveIncr()

    parsed = _parsed(path)

    assert Message("pictograms-not-recognised", {"count": 1}) in parsed.warnings
    assert not parsed.sheet.hazard_statements.drawing_read
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-170")
@pytest.mark.spec("SDB-181")
def test_an_article_gets_no_pictogram_finding(tmp_path: Path) -> None:
    head = [
        *_HEAD[:3],
        "Dieses Produkt ist ein Erzeugnis, deshalb ist es nicht kennzeichnungspflichtig.",
        *_HEAD[3:],
    ]

    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS09"], head=head))

    assert parsed.sheet.stated_article
    assert _findings(parsed) == []


_TEXT = "\n".join([*_HEAD, *_TAIL])


def _extraction() -> ExtractionResult:
    return extraction_from_dict(
        {"text": _TEXT, "extractor": "pymupdf", "pages_sampled": 1, "warnings": []}
    )


@pytest.mark.spec("SDB-179")
@pytest.mark.spec("BIB-25")
def test_a_text_read_without_its_pdf_derives_nothing() -> None:
    reading = read_extraction(_extraction())
    parsed = reading.parser_result
    assert parsed is not None

    label = parsed.sheet.hazard_statements
    assert label.pictograms == []
    assert clp_expected(label).pictograms == ["GHS02", "GHS07"]
    assert not label.drawing_read
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-179", "BIB-24")
def test_kept_pictograms_give_the_reading_of_the_file(tmp_path: Path) -> None:
    path = _sheet(tmp_path / "sheet.pdf", ["GHS02"])
    from_file = read_sheet(path)
    assert from_file.label_images is not None
    kept = label_images_from_dict(label_images_to_dict(from_file.label_images))
    assert from_file.extraction is not None

    again = read_extraction(from_file.extraction, kept)

    assert kept == from_file.label_images
    assert again.parser_result is not None
    assert from_file.parser_result is not None
    assert again.parser_result.sheet == from_file.parser_result.sheet


@pytest.mark.spec("SDB-179", "BIB-24")
def test_the_stage_names_its_version_and_the_pdf_librarys() -> None:
    images = LabelImages(label_images_stage(), LabelImagesStatus.NO_LABEL)

    assert images.stage == label_images_stage()
    assert label_images_stage().endswith(f"+pymupdf-{pymupdf.__version__}")


@pytest.mark.spec("SDW-47")
def test_a_stored_reading_keeps_whether_the_drawing_was_read() -> None:
    reading = read_extraction(_extraction())
    assert reading.parser_result is not None
    assert reading.extraction is not None
    stored = sheet_to_dict(reading.parser_result.sheet, reading.extraction)

    assert "expected_pictograms" not in stored["hazard_statements"]
    assert stored["hazard_statements"]["drawing_read"] is False
    del stored["hazard_statements"]["drawing_read"]
    assert not sheet_from_dict(stored).hazard_statements.drawing_read


@pytest.mark.spec("SDB-180")
@pytest.mark.parametrize(
    "line",
    [
        "Gefahrenpiktogramme entfällt",
        "Piktogramme: nicht erforderlich",
        "Gefahrenpiktogramme\n-",
        "Piktogramme: keine",
        "Kein Piktogramm, kein Signalwort",
        "Gefahrensymbole: entfällt",
    ],
)
def test_a_label_that_says_it_has_no_pictogram(line: str) -> None:
    assert states_no_pictograms(f"{line}\nSignalwort: Achtung\nH319 Reizt")


@pytest.mark.spec("SDB-180")
@pytest.mark.parametrize(
    "line",
    [
        "Gefahrenpiktogramme\nGHS07",
        "Piktogramme GHS07 - Achtung",
        "Symbol R - Sätze",
        "Piktogramm GHS04 nicht auf dem Etikett",
    ],
)
def test_a_label_naming_its_pictograms_says_nothing_of_none(line: str) -> None:
    assert not states_no_pictograms(f"{line}\nH319 Reizt")


@pytest.mark.spec("SDB-180")
@pytest.mark.spec("SDB-181")
def test_a_label_that_says_it_has_no_pictogram_gets_no_missing_one(
    tmp_path: Path,
) -> None:
    tail = ["Gefahrenpiktogramme entfällt", *_TAIL]

    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", [], tail=tail))

    label = parsed.sheet.hazard_statements
    assert label.states_no_pictograms
    assert label.drawing_read
    assert clp_expected(label).pictograms_missing == ["GHS02", "GHS07"]
    assert _findings(parsed) == []


@pytest.mark.spec("BIB-25", "SDB-181", "SDB-183")
def test_a_missing_gas_cylinder_is_neither_expected_nor_a_finding(
    tmp_path: Path,
) -> None:
    """GHS04 may be left out beside the transport label (CLP Article 33)."""
    head = [*_HEAD[:6], "Press. Gas, H280", *_HEAD[7:]]
    tail = ["Signalwort: Achtung", "H280 Enthält Gas unter Druck.", *_TAIL[-3:]]

    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", [], head=head, tail=tail))

    expected = clp_expected(parsed.sheet.hazard_statements)
    assert expected.pictograms == []
    assert expected.pictograms_missing == []
    assert _findings(parsed) == []


@pytest.mark.spec("BIB-25", "SDB-181", "SDB-183")
def test_a_printed_gas_cylinder_is_no_finding(tmp_path: Path) -> None:
    head = [*_HEAD[:6], "Press. Gas, H280", *_HEAD[7:]]
    tail = ["Signalwort: Achtung", "H280 Enthält Gas unter Druck.", *_TAIL[-3:]]

    parsed = _parsed(_sheet(tmp_path / "sheet.pdf", ["GHS04"], head=head, tail=tail))

    assert parsed.sheet.hazard_statements.pictograms == ["GHS04"]
    assert clp_expected(parsed.sheet.hazard_statements).pictograms_not_expected == []
    assert _findings(parsed) == []


def _corrosive_sheet(path: Path, codes: list[str], shown: list[str]) -> Path:
    classes = {
        "H290": "Met. Corr. 1, H290",
        "H318": "Eye Dam. 1, H318",
        "H319": "Eye Irrit. 2, H319",
    }
    head = [*_HEAD[:6], "; ".join(classes[c] for c in codes), *_HEAD[7:]]
    tail = [
        "Signalwort: Achtung",
        *(f"{c} Gefahrenhinweis." for c in codes),
        "P234 Nur in Originalverpackung aufbewahren.",
        *_TAIL[-3:],
    ]
    return _sheet(path, shown, head=head, tail=tail)


@pytest.mark.spec("BIB-25")
@pytest.mark.parametrize(
    ("codes", "pictograms"),
    [
        (["H290"], []),
        (["H290", "H319"], ["GHS07"]),
        (["H290", "H314"], ["GHS05"]),
        (["H290", "H318"], ["GHS05"]),
    ],
)
def test_h290_alone_calls_for_no_ghs05(codes: list[str], pictograms: list[str]) -> None:
    """Annex I 1.3.6 CLP makes GHS05 optional on a package for consumers where
    the product is corrosive to metals only."""
    assert clp_expected(HazardStatements(hazard_codes=codes)).pictograms == pictograms


@pytest.mark.spec("BIB-25", "SDB-181", "SDB-183")
def test_a_label_without_ghs05_for_h290_alone_gets_no_finding(tmp_path: Path) -> None:
    parsed = _parsed(
        _corrosive_sheet(tmp_path / "sheet.pdf", ["H290", "H319"], ["GHS07"])
    )

    assert clp_expected(parsed.sheet.hazard_statements).pictograms_missing == []
    assert _findings(parsed) == []


@pytest.mark.spec("BIB-25", "SDB-181", "SDB-183")
def test_ghs05_printed_for_h290_alone_gets_no_finding(tmp_path: Path) -> None:
    parsed = _parsed(_corrosive_sheet(tmp_path / "sheet.pdf", ["H290"], ["GHS05"]))

    expected = clp_expected(parsed.sheet.hazard_statements)
    assert expected.pictograms == []
    assert expected.pictograms_not_expected == []
    assert _findings(parsed) == []


@pytest.mark.spec("BIB-25", "SDB-181", "SDB-183")
def test_ghs05_printed_for_h290_takes_the_place_of_ghs07(tmp_path: Path) -> None:
    """Printed, GHS05 applies: GHS07 for irritation is not missing beside it."""
    parsed = _parsed(
        _corrosive_sheet(tmp_path / "sheet.pdf", ["H290", "H319"], ["GHS05"])
    )

    assert clp_expected(parsed.sheet.hazard_statements).pictograms_missing == []
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-181")
def test_a_missing_ghs05_beside_h318_is_a_finding(tmp_path: Path) -> None:
    parsed = _parsed(_corrosive_sheet(tmp_path / "sheet.pdf", ["H290", "H318"], []))

    assert _findings(parsed) == [("pictogram-not-found", {"pictogram": "GHS05"})]


_CLASSIFIED = _HEAD[:7]


@pytest.mark.spec("SDB-179", "SDB-187")
def test_pictograms_set_above_the_label_heading_belong_to_the_label(
    tmp_path: Path,
) -> None:
    path = _pages(
        tmp_path / "sheet.pdf",
        [
            *_CLASSIFIED,
            "Gefahrenpiktogramme",
            ["GHS02", "GHS07"],
            "GHS02 GHS07",
            "2.2 Kennzeichnungselemente",
            *_TAIL,
        ],
    )

    images = read_label_images(path)
    parsed = _parsed(path)

    assert images.labels == [["GHS02", "GHS07"]]
    assert parsed.sheet.hazard_statements.pictograms == ["GHS02", "GHS07"]
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-179", "SDB-187")
def test_pictograms_above_the_heading_without_a_title_stay_outside(
    tmp_path: Path,
) -> None:
    path = _pages(
        tmp_path / "sheet.pdf",
        [*_CLASSIFIED, ["GHS06"], "2.2 Kennzeichnungselemente", ["GHS02"], *_TAIL],
    )

    assert read_label_images(path).labels == [["GHS02"]]


@pytest.mark.spec("SDB-179")
@pytest.mark.parametrize(
    "line",
    [
        "Kennzeichnungselemente (CLP):",
        "Besondere Vorschriften für ergänzende Kennzeichnungselemente",
    ],
)
def test_another_line_naming_the_label_elements_starts_no_second_label(
    tmp_path: Path, line: str
) -> None:
    path = _pages(
        tmp_path / "sheet.pdf",
        [*_CLASSIFIED, "2.2. Kennzeichnungselemente", line, ["GHS02", "GHS07"], *_TAIL],
    )

    assert read_label_images(path).labels == [["GHS02", "GHS07"]]


@pytest.mark.spec("SDB-179")
def test_each_sheet_of_a_file_keeps_its_pictograms_under_a_second_heading(
    tmp_path: Path,
) -> None:
    def sheet(name: str, pictograms: list[str]) -> list[str | list[str]]:
        return [
            *_HEAD[:2],
            f"Handelsname: {name}",
            *_CLASSIFIED[3:],
            "2.2. Kennzeichnungselemente",
            "Kennzeichnungselemente (CLP):",
            pictograms,
            *_TAIL,
        ]

    path = _pages(
        tmp_path / "file.pdf",
        sheet("Musterlack", ["GHS02", "GHS07"]),
        sheet("Musterhärter", ["GHS02"]),
    )

    parsed = _parsed(path)

    assert read_label_images(path).labels == [["GHS02", "GHS07"], ["GHS02"]]
    assert [part.sheet.hazard_statements.pictograms for part in parsed.parts] == [
        ["GHS02", "GHS07"],
        ["GHS02"],
    ]
    assert all(part.sheet.hazard_statements.drawing_read for part in parsed.parts)


def _aerosol_sheet(path: Path, codes: list[str], shown: list[str]) -> Path:
    classes = {
        "H222": "Aerosol 1, H222",
        "H229": "H229",
        "H336": "STOT SE 3, H336",
        "H410": "Aquatic Chronic 1, H410",
        "H225": "Flam. Liq. 2, H225",
    }
    head = [*_HEAD[:6], "; ".join(classes[c] for c in codes), *_HEAD[7:]]
    tail = [
        "Signalwort: Gefahr",
        *(f"{c} Gefahrenhinweis." for c in codes),
        "P210 Von Hitze fernhalten. Nicht rauchen.",
        *_TAIL[-3:],
    ]
    return _sheet(path, shown, head=head, tail=tail)


@pytest.mark.spec("SDB-181", "SDB-183")
def test_ghs08_on_an_aerosol_is_no_finding(tmp_path: Path) -> None:
    """Annex I 1.3.3 CLP: an aerosol need not be labelled for the aspiration
    hazard; GHS08 may stand for it where H304 is left out."""
    parsed = _parsed(
        _aerosol_sheet(
            tmp_path / "sheet.pdf",
            ["H222", "H229", "H336", "H410"],
            ["GHS02", "GHS07", "GHS08", "GHS09"],
        )
    )

    label = parsed.sheet.hazard_statements
    assert clp_expected(label).pictograms_not_expected == ["GHS08"]
    assert _findings(parsed) == []


@pytest.mark.spec("SDB-181")
def test_ghs08_without_its_reason_on_another_product_is_a_finding(
    tmp_path: Path,
) -> None:
    parsed = _parsed(
        _aerosol_sheet(tmp_path / "sheet.pdf", ["H225"], ["GHS02", "GHS08"])
    )

    assert _findings(parsed) == [("pictogram-not-expected", {"pictogram": "GHS08"})]
