"""A word broken at a line's end is joined back; a line break that breaks nothing stays."""

from __future__ import annotations

import pytest

from sdb_reader.line_breaks import join_broken_words


@pytest.mark.spec("SDB-54")
@pytest.mark.parametrize(
    ("text", "joined"),
    [
        ("Reakti-\nonen hervorrufen.", "Reaktionen hervorrufen."),
        ("2-Methyl-\n2H-isothiazol-3-on", "2-Methyl-2H-isothiazol-3-on"),
        ("tert-butyl-\n4-hydroxyphenyl", "tert-butyl-4-hydroxyphenyl"),
        ("2-yl)-5-\n(1,1-dimethylethyl)", "2-yl)-5-(1,1-dimethylethyl)"),
        ("2-Methyl-1,2-benzothiazol-3\n(2H)-on", "2-Methyl-1,2-benzothiazol-3(2H)-on"),
        (
            "propionyl-ω-\nhydroxypoly(oxyethylen)",
            "propionyl-ω-hydroxypoly(oxyethylen)",
        ),
        ("Augenschädigung/-\nreizung", "Augenschädigung/-reizung"),
        ("mê-\nme", "même"),
        ("227-813-5\n(R)-p-Mentha-1,8-dien", "227-813-5\n(R)-p-Mentha-1,8-dien"),
        ("Etikettierung\n(+)-Weinsäure", "Etikettierung\n(+)-Weinsäure"),
        ("Haut-\nund Augenschutz", "Haut-\nund Augenschutz"),
        (
            "Dampf nicht einatmen.\n(Fortsetzung)",
            "Dampf nicht einatmen.\n(Fortsetzung)",
        ),
        ("Signalwort -\nGefahr", "Signalwort -\nGefahr"),
    ],
)
def test_a_line_end_inside_a_word_is_joined(text: str, joined: str) -> None:
    assert join_broken_words(text) == joined
