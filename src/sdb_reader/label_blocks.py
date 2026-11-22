"""The heading of a small package's label inside 2.2 (SDB-188).

Both stages that read a label know it: the parser cuts that label from the
text, and the stage that reads the label's drawing (SDB-179) gives the
pictograms below it to that label. One pattern, so the two cut in the same
place; it belongs to both stages' versions.
"""

from __future__ import annotations

import re

# A line that heads the label of a package of at most 125 ml (SDB-188), after
# any bullets: "Kennzeichnung von Verpackungen bei einem Inhalt von nicht mehr
# als 125 ml", "Kennzeichnung gemäß: Ausnahme für Pakete mit einer Kapazität
# von 125 ml oder weniger", "Reduzierte Kennzeichnung (≤ 125 ml):" alone.
SMALL_PACKAGE_HEADING = re.compile(
    r"^[^\S\n]*(?:[·•∙*\-][^\S\n]*)*(?:"
    r"Kennzeichnung\s+von\s+Verpackungen\s+bei\s+einem\s+Inhalt\s+von\s+nicht\s+mehr"
    r"\s+als\s+125\s*ml\b"
    r"|Kennzeichnung\s+gem(?:ä|ae)(?:ß|ss)\s*:\s*Ausnahme\s+f(?:ü|ue)r\s+"
    r"(?:Pakete|Verpackungen)\s+mit\s+einer\s+Kapazit(?:ä|ae)t\s+von\s+125\s*ml"
    r"\s+oder\s+weniger"
    r"|Reduzierte\s+Kennzeichnung\s*\(\s*(?:≤|<=|<)\s*125\s*ml\s*\)\s*:?[^\S\n]*$"
    r")",
    re.IGNORECASE,
)
