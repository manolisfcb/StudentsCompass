"""Rule-based reading of a pasted job description (plan 11 §4.1, C1).

C1 ships before any LLM call exists, so the parse is deterministic: catalogue
skills found line by line, whether each one is required or a nice-to-have,
the title, the seniority and the workplace type. C3 (TASK-089) replaces this
with an LLM parse under the same ``job_description_parses`` row shape; until
then this is what fills it, at zero marginal cost.

The heuristics are deliberately conservative. When a signal is not found the
field is ``None`` and the analysis treats that component as unavailable, rather
than guessing a value the score would then present as a fact.

English and Spanish postings are both read: the users are students in both.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from app.models.skillModel import SkillModel
from app.services.analytics.skillExtractionService import SkillExtractionService

RULES_MODEL_ID = "rules"
#: Bumped whenever the rules below change what they extract. A parse stored
#: under another version is recomputed, never reinterpreted.
RULES_PARSE_VERSION = "jd_rules_v1"

REQUIRED = "required"
PREFERRED = "preferred"
REQUIRED_IMPORTANCE = 1.0
PREFERRED_IMPORTANCE = 0.5

#: Seniority as an ordinal, so a CV and a posting can be compared by distance.
SENIORITY_LEVELS = ("intern", "junior", "mid", "senior", "lead")

_PREFERRED_MARKERS = (
    "nice to have",
    "nice-to-have",
    "preferred",
    "is a plus",
    "a plus",
    "bonus",
    "desirable",
    "would be great",
    "deseable",
    "valorable",
    "se valora",
    "se valorará",
)
_REQUIRED_HEADERS = (
    "requirements",
    "required",
    "must have",
    "must-have",
    "qualifications",
    "what you bring",
    "what we're looking for",
    "what we are looking for",
    "you have",
    "skills",
    "requisitos",
    "imprescindible",
    "buscamos",
    "responsibilities",
    "responsabilidades",
    "funciones",
)
_GENERIC_TITLE_LINES = {
    "about us",
    "about the role",
    "about the job",
    "job description",
    "description",
    "overview",
    "the role",
    "descripción",
    "descripción del puesto",
    "sobre nosotros",
}

_SENIORITY_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("intern", re.compile(r"\b(intern|internship|trainee|working student|pr[aá]cticas|becari[oa])\b")),
    ("lead", re.compile(r"\b(lead|principal|staff|head of|manager|director)\b")),
    ("senior", re.compile(r"\b(senior|sr\.?)\b")),
    ("junior", re.compile(r"\b(junior|jr\.?|entry[- ]level|graduate|new grad)\b")),
    ("mid", re.compile(r"\b(mid[- ]level|intermediate|semi[- ]?senior|ssr)\b")),
)
_YEARS = re.compile(
    r"(\d{1,2})\s*\+?\s*(?:-\s*\d{1,2}\s*)?(?:years?|yrs?|años?)",
    re.IGNORECASE,
)
_WORKPLACE_PATTERNS: tuple[tuple[str, re.Pattern], ...] = (
    ("hybrid", re.compile(r"\b(hybrid|h[ií]brido)\b")),
    ("remote", re.compile(r"\b(remote|remoto|teletrabajo|work from home)\b")),
    ("onsite", re.compile(r"\b(on[- ]?site|in[- ]office|presencial)\b")),
)


#: How much of the role's own text is embedded for context similarity.
ROLE_TEXT_MAX_CHARS = 3000

# Sections of a posting that describe the employer rather than the role.
_EMPLOYER_SECTION = re.compile(
    r"^(about (?!the (role|team|job|position)|you\b|this (role|job|position))\S|who we are|"
    r"our (story|mission|company|values|commitment)|benefits|perks|compensation|"
    r"pay (range|transparency)|salary|equal (employment )?opportunit|we are an equal|eeo\b|"
    r"accommodations?|why (join|work)|life at|what we offer|total rewards|the annual salary|"
    r"base salary|privacy|diversity|sobre nosotros|qui[eé]nes somos|beneficios|"
    r"qu[eé] ofrecemos|igualdad de oportunidades)",
    re.IGNORECASE,
)
# Sections that describe the role, which end an employer section.
_ROLE_SECTION = re.compile(
    r"^(what you('ll)? (do|bring|need)|responsibilit|requirements|qualifications|"
    r"you (will|might|have|bring)|who you are|minimum|preferred|nice to have|"
    r"about the (role|team|job|position)|the role|in this role|"
    r"what we('re| are) looking for|about you|requisitos|responsabilidades|funciones|"
    r"buscamos|el puesto|tu rol)",
    re.IGNORECASE,
)


def role_text(title: str | None, text: str) -> str:
    """The part of a posting that describes the role, for embedding.

    Measured on 168 real CV × posting pairs (TASK-079): embedding the whole
    posting separated aligned from unrelated roles with an AUC of 0.84, because
    benefits, equal-opportunity and "about us" text is shared by every posting
    of an employer and dominates the vector. Dropping those sections and
    keeping the first 3000 characters of the rest raised it to 0.94.
    """
    keep = [title] if title else []
    skipping = False
    for raw in text.split("\n"):
        line = raw.strip()
        if not line:
            continue
        if len(line) <= 80 and _EMPLOYER_SECTION.search(line):
            skipping = True
            continue
        if len(line) <= 80 and _ROLE_SECTION.search(line):
            skipping = False
        if not skipping:
            keep.append(line)
    return "\n".join(keep)[:ROLE_TEXT_MAX_CHARS].strip()


@dataclass
class ParsedRequirement:
    skill_id: str
    display_name: str
    normalized_name: str
    category: str | None
    requirement: str
    importance_score: float
    evidence_text: str


@dataclass
class ParsedJobDescription:
    title: str | None
    seniority: str | None
    min_years: int | None
    workplace_type: str | None
    requirements: list[ParsedRequirement] = field(default_factory=list)

    def to_json(self) -> dict:
        return {**asdict(self), "parser": RULES_PARSE_VERSION}


def years_to_level(years: int | None) -> str | None:
    if years is None:
        return None
    if years <= 1:
        return "junior"
    if years <= 4:
        return "mid"
    if years <= 7:
        return "senior"
    return "lead"


def detect_seniority(text: str) -> str | None:
    lowered = text.lower()
    for level, pattern in _SENIORITY_PATTERNS:
        if pattern.search(lowered):
            return level
    return None


def detect_min_years(text: str) -> int | None:
    years = [int(match.group(1)) for match in _YEARS.finditer(text)]
    years = [value for value in years if value <= 30]
    return min(years) if years else None


def detect_workplace_type(text: str) -> str | None:
    lowered = text.lower()
    for kind, pattern in _WORKPLACE_PATTERNS:
        if pattern.search(lowered):
            return kind
    return None


def detect_title(lines: list[str]) -> str | None:
    for line in lines[:8]:
        candidate = line.strip(" -•*#:\t")
        if not candidate or len(candidate) > 120:
            continue
        if candidate.lower() in _GENERIC_TITLE_LINES:
            continue
        return candidate
    return None


def _is_header(line: str) -> bool:
    return len(line) <= 60 and (line.endswith(":") or len(line.split()) <= 6)


#: A header that opens a section saying nothing about requirements.
_CONTEXT_MARKER = "context"


def _line_marker(line: str) -> str | None:
    lowered = line.lower()
    if any(marker in lowered for marker in _PREFERRED_MARKERS):
        return PREFERRED
    if _is_header(line) and any(header in lowered for header in _REQUIRED_HEADERS):
        return REQUIRED
    if _is_header(line) and (
        lowered.strip(" :") in _GENERIC_TITLE_LINES or lowered.startswith(("about ", "sobre "))
    ):
        return _CONTEXT_MARKER
    return None


async def parse_job_description(
    text: str,
    *,
    extractor: SkillExtractionService,
    lookup: dict[str, SkillModel] | None = None,
) -> ParsedJobDescription:
    """Read ``text`` (already normalized) into a :class:`ParsedJobDescription`.

    A header line switches the section that follows it; a line that itself
    says "nice to have" marks only its own skills. A skill seen as required
    anywhere stays required: the stricter reading wins.

    When the posting has an explicit requirements section, a skill mentioned
    only outside it (the intro, "about the role") is read as a nice-to-have:
    "you will turn sales data into decisions" does not require Sales. A posting
    with no sections at all is read as all required, since nothing says
    otherwise.
    """
    lines = [line.strip() for line in text.split("\n")]
    if lookup is None:
        lookup = await extractor.build_skill_lookup()

    structured = any(_line_marker(line) == REQUIRED for line in lines if line)
    outside = PREFERRED if structured else REQUIRED
    section = outside
    found: dict[str, ParsedRequirement] = {}
    for line in lines:
        if not line:
            continue
        marker = _line_marker(line)
        if marker is not None and _is_header(line):
            section = outside if marker == _CONTEXT_MARKER else marker
        requirement = PREFERRED if marker == PREFERRED else section
        for match in await extractor.extract_known_skills_from_text(
            line, lookup=lookup, extraction_method=RULES_PARSE_VERSION
        ):
            skill_id = str(match.skill.id)
            existing = found.get(skill_id)
            if existing is not None and existing.requirement == REQUIRED:
                continue
            found[skill_id] = ParsedRequirement(
                skill_id=skill_id,
                display_name=match.skill.display_name,
                normalized_name=match.skill.normalized_name,
                category=match.skill.category,
                requirement=requirement,
                importance_score=REQUIRED_IMPORTANCE if requirement == REQUIRED else PREFERRED_IMPORTANCE,
                evidence_text=line[:240],
            )

    title = detect_title(lines)
    min_years = detect_min_years(text)
    # The title, then the years asked for. Never the body's wording: "report to
    # the hiring manager" or "work with senior stakeholders" are not the level
    # of the role, and a wrong level is worse than none.
    seniority = detect_seniority(title or "") or years_to_level(min_years)

    requirements = sorted(
        found.values(),
        key=lambda item: (item.requirement != REQUIRED, item.display_name.lower()),
    )
    return ParsedJobDescription(
        title=title,
        seniority=seniority,
        min_years=min_years,
        workplace_type=detect_workplace_type(text),
        requirements=requirements,
    )
