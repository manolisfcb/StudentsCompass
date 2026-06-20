from __future__ import annotations


class SkillGapScoringService:
    """Phase 5 scoring for prioritizing missing role skills."""

    MARKET_DEMAND_WEIGHT = 0.35
    WEAK_MATCH_EVIDENCE_WEIGHT = 0.35

    @classmethod
    def prioritize_missing_skills(cls, missing_skills: list[dict]) -> list[dict]:
        prioritized = [cls.score_missing_skill(skill) for skill in missing_skills]
        prioritized.sort(
            key=lambda skill: (
                -skill["skill_gap_score"],
                -skill["required_skill_weight"],
                skill["display_name"].lower(),
            )
        )
        for index, skill in enumerate(prioritized, start=1):
            skill["priority_rank"] = index
        return prioritized

    @classmethod
    def score_missing_skill(cls, skill: dict) -> dict:
        importance = cls._clamp(float(skill.get("importance_score") or 0.75), 0.05, 1.0)
        demand_score = cls._clamp(float(skill.get("market_demand_score") or 0.0), 0.0, 1.0)
        required_skill_weight = importance * (1.0 + demand_score * cls.MARKET_DEMAND_WEIGHT)
        student_skill_evidence = cls._student_skill_evidence(skill)
        skill_gap_score = required_skill_weight * (1.0 - student_skill_evidence)

        return {
            **skill,
            "required_skill_weight": round(required_skill_weight, 4),
            "student_skill_evidence": round(student_skill_evidence, 4),
            "skill_gap_score": round(skill_gap_score, 4),
            "priority_score": round(skill_gap_score, 4),
            "priority_rank": 0,
            "reason": cls._reason(
                skill=skill,
                required_skill_weight=required_skill_weight,
                student_skill_evidence=student_skill_evidence,
            ),
        }

    @classmethod
    def _student_skill_evidence(cls, skill: dict) -> float:
        similarity_score = cls._clamp(float(skill.get("similarity_score") or 0.0), 0.0, 1.0)
        if skill.get("match_type") == "weak" and similarity_score:
            return cls._clamp(similarity_score * cls.WEAK_MATCH_EVIDENCE_WEIGHT, 0.0, 0.45)
        return 0.0

    @staticmethod
    def _reason(
        *,
        skill: dict,
        required_skill_weight: float,
        student_skill_evidence: float,
    ) -> str:
        demand_count = int(skill.get("market_demand_count") or 0)
        demand_clause = (
            f" and appears in {demand_count} synced market posting(s)"
            if demand_count
            else ""
        )
        evidence_clause = (
            " Only weak transferable evidence was found, so it remains a gap."
            if student_skill_evidence
            else ""
        )
        return (
            f"{skill['display_name']} has a required-skill weight of "
            f"{required_skill_weight:.2f}{demand_clause} for this role."
            f"{evidence_clause}"
        )

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))
