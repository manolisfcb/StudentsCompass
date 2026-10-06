"""Deterministic analysis of a pasted vacancy against a CV (plan 11 §4.1, TASK-079).

No LLM is involved and the marginal cost is zero (at most one embedding of a
posting nobody has pasted before). It answers the first question of plan 11
§1 — does this vacancy fit me, and why — with the engine that already exists:

    score = gate × Σ wᵢ · componentᵢ      (weights: ``config.JOB_MATCH_WEIGHTS``)

    skills     importance-weighted coverage of the posting's catalogue skills,
               with partial credit for semantic and weak matches
               (``SemanticMatchingService``)
    context    CV summary ↔ posting cosine, rescaled per model
               (``SimilarityProfile``)
    title      how much of the posting's role title the CV summary names
    seniority  distance between the level asked for and the CV's level

A component without a signal (no catalogue skill found, no real-vector
provider, no CV summary, no level in the posting) is reported as unavailable
and its weight is spread over the others. It is never filled with a guess,
because the number is shown to the user as an assessment of them.

The score is never shown bare: it always travels with its band and the
breakdown that produced it (plan 11 §4.1, §12).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app import config
from app.models.jobTargetModel import JobDescriptionParseModel, JobTargetModel
from app.models.resumeModel import ResumeModel
from app.services.analytics.embeddingService import (
    HASH_MODEL_NAME,
    ResumeEmbeddingService,
    generate_embedding_with_model,
    get_effective_model_name,
    is_semantic_matching_ready,
)
from app.services.analytics.resumeSkillExtractionService import ResumeSkillExtractionService
from app.services.analytics.resumeSkillReviewService import ResumeSkillReviewService
from app.services.analytics.semanticMatchingService import SemanticMatchingService
from app.services.analytics.skillExtractionService import SkillExtractionService
from app.services.analytics.skillGapScoringService import SkillGapScoringService
from app.services.careerLab.jobDescriptionRules import (
    REQUIRED,
    RULES_MODEL_ID,
    RULES_PARSE_VERSION,
    SENIORITY_LEVELS,
    detect_seniority,
    parse_job_description,
    role_text,
    years_to_level,
)
from app.services.careerLab.jobTargetService import JobTargetService, normalize_job_text

LOGGER = logging.getLogger(__name__)

ANALYSIS_VERSION = "job_target_v1"
COMPONENTS = ("skills", "context", "title", "seniority")

BAND_STRONG = "strong_match"
BAND_MATCH = "match"
BAND_WEAK = "weak_match"

_TITLE_NOISE = {
    "intern", "internship", "trainee", "junior", "jr", "senior", "sr", "lead",
    "principal", "staff", "mid", "level", "entry", "graduate", "i", "ii", "iii",
    "iv", "remote", "hybrid", "onsite", "m", "f", "d", "w", "x", "and", "or",
    "the", "a", "of", "for", "in", "y", "de", "del", "la", "el", "en", "para",
    "con", "full", "time", "part", "contract", "temporary",
}
_WORD = re.compile(r"[a-záéíóúñü0-9+#]+")
_YEARS_IN_CV = re.compile(r"(\d{1,2})\s*\+?\s*(?:years?|yrs?|años?)", re.IGNORECASE)
_STUDENT_MARKERS = re.compile(
    r"\b(student|undergraduate|recent graduate|bachelor'?s? student|estudiante|"
    r"reci[eé]n graduad[oa]|bootcamp)\b",
    re.IGNORECASE,
)


class JobTargetAnalysisError(RuntimeError):
    """The analysis could not be produced; the message is safe to show."""


def band_for(score: float | None) -> str | None:
    if score is None:
        return None
    if score >= config.JOB_MATCH_STRONG_THRESHOLD:
        return BAND_STRONG
    if score >= config.JOB_MATCH_THRESHOLD:
        return BAND_MATCH
    return BAND_WEAK


#: Catalogue requirements (required = 1, nice-to-have = 0.5) needed before the
#: skills component carries its full weight. One matched skill out of one found
#: is not 100 % coverage of a posting; it is a posting the catalogue barely
#: reads. Measured on a real legal posting where the only catalogue skill found
#: was "Sales": the skills component alone put it at 0.75.
FULL_SKILL_EVIDENCE = 3.0


def skill_evidence(requirements: list[dict]) -> float:
    """0–1: how much of its configured weight the skills component may carry."""
    found = sum(float(item.get("importance_score") or 0.0) for item in requirements)
    return round(min(1.0, found / FULL_SKILL_EVIDENCE), 4)


def combine(
    components: dict[str, float | None],
    *,
    gate: float = 1.0,
    confidence: dict[str, float] | None = None,
) -> dict:
    """The weighted score over the components that have a value.

    ``confidence`` scales a component's configured weight down when its signal
    is thin (see ``skill_evidence``); the freed weight goes to the others, as
    an unavailable component's does. Returns the score (or ``None`` when no
    component is available) and the effective weight each one carried.
    """
    weights = {
        name: weight * (confidence or {}).get(name, 1.0)
        for name, weight in zip(COMPONENTS, config.JOB_MATCH_WEIGHTS)
    }
    available = {name: value for name, value in components.items() if value is not None}
    total = sum(weights[name] for name in available)
    if not available or total <= 0:
        return {"score": None, "effective_weights": {name: 0.0 for name in COMPONENTS}}
    effective = {
        name: (weights[name] / total if name in available else 0.0) for name in COMPONENTS
    }
    score = gate * sum(effective[name] * value for name, value in available.items())
    return {
        "score": round(max(0.0, min(score, 1.0)), 4),
        "effective_weights": {name: round(value, 4) for name, value in effective.items()},
        "weights": dict(zip(COMPONENTS, config.JOB_MATCH_WEIGHTS)),
    }


def title_tokens(title: str | None) -> list[str]:
    words = _WORD.findall((title or "").lower())
    return [word for word in words if word not in _TITLE_NOISE and len(word) > 1]


def title_affinity(title: str | None, cv_text: str | None) -> float | None:
    """Share of the posting's role words that the CV summary names."""
    tokens = title_tokens(title)
    if not tokens or not (cv_text or "").strip():
        return None
    cv_words = set(_WORD.findall(cv_text.lower()))
    return round(sum(1 for token in tokens if token in cv_words) / len(tokens), 4)


def cv_seniority(cv_text: str | None) -> str | None:
    text = cv_text or ""
    years = [int(match.group(1)) for match in _YEARS_IN_CV.finditer(text) if int(match.group(1)) <= 40]
    if years:
        return years_to_level(max(years))
    explicit = detect_seniority(text)
    if explicit in {"intern", "junior"}:
        return explicit
    if _STUDENT_MARKERS.search(text):
        return "junior"
    return None


def seniority_fit(asked: str | None, has: str | None) -> float | None:
    """1 at or below the CV's level, 0.5 one step above, 0 further."""
    if asked is None or has is None:
        return None
    gap = SENIORITY_LEVELS.index(asked) - SENIORITY_LEVELS.index(has)
    if gap <= 0:
        return 1.0
    return 0.5 if gap == 1 else 0.0


class JobTargetAnalysisService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.targets = JobTargetService(session)
        self.review = ResumeSkillReviewService(session)
        self.extraction = ResumeSkillExtractionService(session, review=self.review)

    # -- the shared parse ------------------------------------------------------

    async def ensure_parse(self, target: JobTargetModel) -> JobDescriptionParseModel:
        """The rules parse of the target's text, shared, with its vector if any.

        Built once per distinct text. A parse produced by an older version of
        the rules is rebuilt; one that predates the real-vector provider gets
        its vector filled in. Neither path touches other users' targets.
        """
        parse = await self.targets.get_parse(target.text_hash)
        stale = (
            parse is not None
            and parse.model_id == RULES_MODEL_ID
            and parse.prompt_version != RULES_PARSE_VERSION
        )
        if parse is None or stale:
            normalized = normalize_job_text(target.raw_text)
            parsed = await parse_job_description(
                normalized, extractor=SkillExtractionService(self.session)
            )
            if parse is None:
                parse = await self.targets.store_parse(
                    text_hash=target.text_hash,
                    parsed=parsed.to_json(),
                    model_id=RULES_MODEL_ID,
                    prompt_version=RULES_PARSE_VERSION,
                    source=target.source,
                )
            else:
                await self._replace_parse(parse.text_hash, parsed.to_json())
                parse = await self.targets.get_parse(target.text_hash)

        active_model = get_effective_model_name()
        if (
            is_semantic_matching_ready()
            and parse.embedding_model_name != active_model
            and active_model != HASH_MODEL_NAME
        ):
            text = role_text((parse.parsed or {}).get("title"), normalize_job_text(target.raw_text))
            result = await generate_embedding_with_model(text)
            if result is not None and result[1] == active_model:
                await self._attach_embedding(parse.text_hash, result[0], active_model)
                parse = await self.targets.get_parse(target.text_hash)
        return parse

    async def _replace_parse(self, text_hash: str, parsed: dict) -> None:
        await self.session.execute(
            update(JobDescriptionParseModel)
            .where(JobDescriptionParseModel.text_hash == text_hash)
            # The vector was made from the old reading's role text: drop it so
            # it is rebuilt from the new one, never kept beside a newer parse.
            .values(
                parsed=parsed,
                prompt_version=RULES_PARSE_VERSION,
                embedding=None,
                embedding_model_name=None,
                updated_at=datetime.utcnow(),
            )
            .execution_options(synchronize_session=False)
        )
        await self.session.commit()

    async def _attach_embedding(self, text_hash: str, vector: list[float], model_name: str) -> None:
        await self.session.execute(
            update(JobDescriptionParseModel)
            .where(JobDescriptionParseModel.text_hash == text_hash)
            .values(embedding=vector, embedding_model_name=model_name, updated_at=datetime.utcnow())
            .execution_options(synchronize_session=False)
        )
        await self.session.commit()

    # -- the analysis ------------------------------------------------------------

    async def _refresh_cv_skills(self, resume: ResumeModel, *, user_id: UUID) -> None:
        """Read the CV against the catalogue as it is now, not as it was.

        A CV extracted before the catalogue grew (TASK-082) would show every
        newly catalogued skill it mentions as a gap. Re-reading the summary is
        rules only and additive — what the student confirmed or rejected keeps
        its status — which is what Career Lab's skills sync already does. A CV
        without a summary is read from its file only the first time, as
        before: that costs a download from storage.
        """
        if resume.ai_summary:
            await self.extraction.extract_resume_skills_from_text(
                resume_id=resume.id,
                user_id=user_id,
                text=resume.ai_summary,
                extraction_method="resume_summary_rules_v1",
                source_section="ai_summary",
            )
            return
        await self.extraction._extract_from_resume_summary_if_needed(resume=resume, user_id=user_id)

    async def analyze(self, target: JobTargetModel, resume: ResumeModel) -> dict:
        parse = await self.ensure_parse(target)
        parsed = parse.parsed or {}
        requirements = list(parsed.get("requirements") or [])

        await self._refresh_cv_skills(resume, user_id=target.user_id)
        current_skills = await self.review.get_resume_skills(resume.id)

        matcher = SemanticMatchingService(session=self.session)
        match = await matcher.analyze_required_skill_matches(
            current_skills=current_skills, required_skills=requirements
        )
        context = await self._context(matcher, resume=resume, parse=parse)

        cv_text = resume.ai_summary
        asked_level = parsed.get("seniority")
        has_level = cv_seniority(cv_text)
        components = {
            "skills": match.match_score if requirements else None,
            "context": context["value"],
            "title": title_affinity(parsed.get("title"), cv_text),
            "seniority": seniority_fit(asked_level, has_level),
        }
        combined = combine(components, confidence={"skills": skill_evidence(requirements)})
        score = combined["score"]

        weak_by_id = {str(item["skill_id"]): item for item in match.weak_matched_skills}
        gaps = SkillGapScoringService.prioritize_missing_skills(
            [
                {**skill, **weak_by_id.get(str(skill["skill_id"]), {})}
                for skill in match.missing_skills
            ]
        )
        required_total = sum(1 for item in requirements if item.get("requirement") == REQUIRED)
        required_covered = sum(
            1 for item in match.matched_required_skills if item.get("requirement") == REQUIRED
        )

        return {
            "analysis_version": ANALYSIS_VERSION,
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "resume_id": str(resume.id),
            "score": score,
            "band": band_for(score),
            "gate": {"value": 1.0, "reason": "no_preferences_declared"},
            "components": {
                name: {
                    "value": components[name],
                    "available": components[name] is not None,
                    "weight": combined.get("weights", {}).get(name, 0.0),
                    "effective_weight": combined["effective_weights"][name],
                }
                for name in COMPONENTS
            },
            "context": context,
            "seniority": {"asked": asked_level, "cv": has_level, "min_years": parsed.get("min_years")},
            "title": parsed.get("title"),
            "workplace_type": parsed.get("workplace_type"),
            "requirements": {
                "evidence": skill_evidence(requirements),
                "required": required_total,
                "preferred": len(requirements) - required_total,
                "required_covered": required_covered,
            },
            "strengths": [self._strength(item) for item in match.matched_required_skills],
            "gaps": [self._gap(item) for item in gaps],
            "semantic_matching_ready": is_semantic_matching_ready(),
            "parse_version": parse.prompt_version,
        }

    async def _context(self, matcher: SemanticMatchingService, *, resume: ResumeModel, parse) -> dict:
        unavailable = {"value": None, "level": "unavailable", "message": None}
        if not is_semantic_matching_ready() or parse.embedding is None:
            return {**unavailable, "message": "Context similarity needs a semantic embedding provider."}
        if not (resume.ai_summary or "").strip():
            return {**unavailable, "message": "The CV has no summary to compare yet."}
        stored = await ResumeEmbeddingService(self.session).upsert_resume_embedding_from_text(
            resume_id=resume.id, text=resume.ai_summary
        )
        if (
            stored is None
            or stored.embedding is None
            or stored.model_name != parse.embedding_model_name
        ):
            return {**unavailable, "message": "The CV could not be embedded right now."}
        summary = matcher.context_from_vectors(
            list(stored.embedding), list(parse.embedding), evidence_sources=["resume_summary", "job_description"]
        )
        return {
            "value": summary.context_similarity_score,
            "level": summary.context_match_level,
            "message": summary.message,
        }

    @staticmethod
    def _strength(item: dict) -> dict:
        return {
            "skill_id": str(item["skill_id"]),
            "display_name": item["display_name"],
            "requirement": item.get("requirement"),
            "match_type": item.get("match_type") or "exact",
            "matched_with": item.get("matched_skill_display_name"),
            "similarity": item.get("similarity_score"),
        }

    @staticmethod
    def _gap(item: dict) -> dict:
        reinforce = item.get("match_type") == "weak"
        return {
            "skill_id": str(item["skill_id"]),
            "display_name": item["display_name"],
            "requirement": item.get("requirement"),
            "kind": "reinforce" if reinforce else "gap",
            "closest_skill": item.get("matched_skill_display_name") if reinforce else None,
            "similarity": item.get("similarity_score") if reinforce else None,
            "priority_rank": item["priority_rank"],
            "skill_gap_score": item["skill_gap_score"],
            "reason": item["reason"],
        }

    # -- the whole flow, inline ---------------------------------------------------

    async def run(self, *, target: JobTargetModel, resume: ResumeModel) -> JobTargetModel:
        """Claim, analyse and settle one target in the request.

        C1 is deterministic and fast, so it runs inline; the lease still guards
        it, so two concurrent runs of one target cannot both write. From C3 on
        the LLM parse moves behind the same lease into the worker.
        """
        # Read before anything can roll back: a rollback expires these objects,
        # and an expired attribute would be lazily loaded outside the loop.
        target_id: UUID = target.id
        user_id: UUID = target.user_id
        if not await self.targets.claim(target_id):
            raise JobTargetAnalysisError("This job description is already being analysed.")
        try:
            snapshot = await self.analyze(target, resume)
        except Exception:
            LOGGER.exception("job target analysis failed: target=%s", target_id)
            await self.session.rollback()
            await self.targets.fail(
                target_id, "We could not analyse this job description. Please try again."
            )
        else:
            parsed_title = snapshot.get("title")
            await self.targets.complete(
                target_id,
                match_snapshot=snapshot,
                title=(parsed_title or None) and parsed_title[:255],
                workplace_type=snapshot.get("workplace_type"),
            )
        refreshed = await self.targets.get_user_target(target_id=target_id, user_id=user_id)
        assert refreshed is not None
        await self.session.refresh(refreshed)
        return refreshed
