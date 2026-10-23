from __future__ import annotations

import re


def normalize_identifier(value: object) -> str:
    """Normalize patent/application/registration numbers for matching.

    Keeps only letters and digits, uppercases `x`, removes CN and punctuation.
    Examples:
    - 209910000001.1 -> 2099100000011
    - 209930000005.X -> 209930000005X
    """

    text = str(value or "").strip().upper()
    text = re.sub(r"\s+", "", text)
    text = text.removeprefix("CN")
    return re.sub(r"[^0-9A-Z]", "", text)


def compact_text(value: object) -> str:
    return re.sub(r"\s+", "", str(value or "").strip())


def display_identifier(value: object) -> str:
    return str(value or "").strip()

