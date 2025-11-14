"""
===============================================================================
DocumentType – canonical document type codes for lifecycle
-------------------------------------------------------------------------------
Project types:
  FB, AA, VA, LS, AM, EXT, PR, XO, QMH, OTHER
We provide a 2-letter mapping function from the parsed code segment.
===============================================================================
"""
from __future__ import annotations
from enum import Enum


class DocumentType(Enum):
    FB = "FB"       # Formblatt
    AA = "AA"       # Arbeitsanweisung
    VA = "VA"       # Verfahrensanweisung
    LS = "LS"       # Liste
    AM = "AM"       # Aide-Memoire
    EXT = "EXT"     # externes Dokument
    PR = "PR"       # Protokoll
    XO = "XO"       # externes Bestellformular
    QMH = "QMH"     # Qualitätsmanagementhandbuch
    OTHER = "OTHER"


def from_two_letter_code(tt2: str | None) -> "DocumentType":
    """
    Map the two-letter token to a DocumentType.

    Rules:
      - Exact matches: FB, AA, VA, LS, AM, PR, XO
      - EX -> EXT
      - QM -> QMH
      - else OTHER
    """
    if not tt2:
        return DocumentType.OTHER
    key = tt2.strip().upper()
    if key in {"FB", "AA", "VA", "LS", "AM", "PR", "XO"}:
        return DocumentType[key]
    if key == "EX":
        return DocumentType.EXT
    if key == "QM":
        return DocumentType.QMH
    return DocumentType.OTHER
