"""Every questionnaire definition the product has ever served, indexed by version.

A stored ``user_questionnaires`` row carries the ``version`` it was answered
under, but the profile endpoint rendered it against whatever definition happens
to be current. So after a questionnaire is revised, an old profile shows the new
questions beside the old answers: option ids that no longer exist, questions the
user never saw, and a set of results that cannot be derived from either.

The answers and the results are a historical snapshot. The definition that
produced them has to be one too, so the files are indexed by the ``version``
they *declare* rather than by their filename — the current file is
``v1/v2.json`` and declares ``"version": "v3"``, and a lookup keyed on paths
would be keyed on a lie.
"""
from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

LOGGER = logging.getLogger(__name__)

#: Where the definitions live. Every ``*.json`` below this is a candidate.
QUESTIONNAIRE_ROOT = Path("app/data/questionnaires")

#: The definition new submissions are scored against.
CURRENT_QUESTIONNAIRE_PATH = QUESTIONNAIRE_ROOT / "v1" / "v2.json"


class QuestionnaireVersionNotFound(LookupError):
    """No definition on disk declares this version.

    Raised rather than falling back to the current definition: rendering old
    answers against new questions is the defect this module exists to fix, and
    silently doing it is worse than saying the version is gone.
    """

    def __init__(self, version: str, available: tuple[str, ...]):
        super().__init__(
            f"No questionnaire definition declares version {version!r}; "
            f"available: {', '.join(available) or 'none'}"
        )
        self.version = version
        self.available = available


def _read(path: Path) -> dict:
    with open(path, "r") as handle:
        return json.load(handle)


@lru_cache(maxsize=1)
def _definitions_by_version() -> dict[str, dict]:
    """Every definition on disk, keyed by its declared version.

    Cached: the files ship with the image and do not change under a running
    process. Two files declaring the same version is a packaging mistake — the
    first one found wins and the collision is logged, because guessing between
    them silently would make scoring depend on directory order.
    """
    definitions: dict[str, dict] = {}
    if not QUESTIONNAIRE_ROOT.exists():
        return definitions

    for path in sorted(QUESTIONNAIRE_ROOT.rglob("*.json")):
        try:
            data = _read(path)
        except (OSError, json.JSONDecodeError):
            LOGGER.exception("Questionnaire definition could not be read: %s", path)
            continue
        version = data.get("version")
        if not version:
            LOGGER.warning("Questionnaire definition without a version, ignored: %s", path)
            continue
        if version in definitions:
            LOGGER.warning(
                "Two questionnaire definitions declare version %s; keeping the first. "
                "Duplicate: %s",
                version,
                path,
            )
            continue
        definitions[version] = data
    return definitions


def available_versions() -> tuple[str, ...]:
    return tuple(sorted(_definitions_by_version()))


def load_current_definition() -> dict:
    """The definition new submissions are scored against."""
    if not CURRENT_QUESTIONNAIRE_PATH.exists():
        raise FileNotFoundError(
            f"Questionnaire file not found at {CURRENT_QUESTIONNAIRE_PATH}"
        )
    return _read(CURRENT_QUESTIONNAIRE_PATH)


def load_definition_for_version(version: str) -> dict:
    """The definition a stored answer set was taken under."""
    definitions = _definitions_by_version()
    if version not in definitions:
        raise QuestionnaireVersionNotFound(version, available_versions())
    return definitions[version]


def reset_cache() -> None:
    """Forget what was read from disk. For tests that write definitions."""
    _definitions_by_version.cache_clear()
