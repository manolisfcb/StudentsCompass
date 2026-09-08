from __future__ import annotations

import re


PHONE_PATTERN = re.compile(
    r"(?:(?:\+?\d{1,3}[\s().-]*)?(?:\(?\d{2,4}\)?[\s().-]*){2,5}\d{2,4})"
)


def extract_phone_number(text: str | None) -> str | None:
    if not text:
        return None

    for match in PHONE_PATTERN.finditer(text):
        raw = match.group(0).strip()
        digits = re.sub(r"\D", "", raw)
        if len(digits) < 10 or len(digits) > 15:
            continue

        normalized = re.sub(r"\s+", " ", raw)
        normalized = normalized.strip(".,;:")
        return normalized

    return None
