from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.skillModel import CourseModel, CourseSkillModel, JobSkillModel, SkillAliasModel, SkillModel


CAPSTONE_SKILL_SEED_DATA: list[dict[str, Any]] = [
    {"name": "python", "display": "Python", "category": "programming", "aliases": ["python 3", "python programming"]},
    {"name": "sql", "display": "SQL", "category": "data", "aliases": ["structured query language", "postgresql sql"]},
    {"name": "excel", "display": "Excel", "category": "business_tools", "aliases": ["microsoft excel", "spreadsheets"]},
    {"name": "power_bi", "display": "Power BI", "category": "analytics_tools", "aliases": ["microsoft power bi", "powerbi"]},
    {"name": "tableau", "display": "Tableau", "category": "analytics_tools", "aliases": ["tableau desktop"]},
    {"name": "data_visualization", "display": "Data Visualization", "category": "analytics", "aliases": ["dashboarding", "charts"]},
    {"name": "statistics", "display": "Statistics", "category": "analytics", "aliases": ["statistical analysis", "descriptive statistics"]},
    {"name": "data_cleaning", "display": "Data Cleaning", "category": "analytics", "aliases": ["data wrangling", "data preprocessing"]},
    {"name": "data_modeling", "display": "Data Modeling", "category": "data", "aliases": ["dimensional modeling"]},
    {"name": "etl", "display": "ETL", "category": "data_engineering", "aliases": ["extract transform load", "data pipelines"]},
    {"name": "business_analysis", "display": "Business Analysis", "category": "business", "aliases": ["requirements analysis"]},
    {"name": "requirements_gathering", "display": "Requirements Gathering", "category": "business", "aliases": ["requirements elicitation"]},
    {"name": "stakeholder_management", "display": "Stakeholder Management", "category": "business", "aliases": ["stakeholder communication"]},
    {"name": "kpi_design", "display": "KPI Design", "category": "business", "aliases": ["metrics design", "performance indicators"]},
    {"name": "agile", "display": "Agile", "category": "delivery", "aliases": ["scrum", "agile methodology"]},
    {"name": "machine_learning", "display": "Machine Learning", "category": "data_science", "aliases": ["ml", "predictive modeling"]},
    {"name": "pandas", "display": "Pandas", "category": "programming", "aliases": ["python pandas"]},
    {"name": "numpy", "display": "NumPy", "category": "programming", "aliases": ["python numpy"]},
    {"name": "scikit_learn", "display": "Scikit-learn", "category": "data_science", "aliases": ["sklearn", "scikit learn"]},
    {"name": "communication", "display": "Communication", "category": "soft_skills", "aliases": ["written communication", "presentation skills"]},
    {"name": "problem_solving", "display": "Problem Solving", "category": "soft_skills", "aliases": ["analytical thinking"]},
    {"name": "canadian_labor_market", "display": "Canadian Labor Market", "category": "career", "aliases": ["canadian job market"]},
    {"name": "resume_tailoring", "display": "Resume Tailoring", "category": "career", "aliases": ["cv tailoring", "ats resume"]},
    {"name": "interview_preparation", "display": "Interview Preparation", "category": "career", "aliases": ["mock interview"]},
    {"name": "github", "display": "GitHub", "category": "technical_tools", "aliases": ["git", "version control"]},
]


CAPSTONE_COURSE_SEED_DATA: list[dict[str, Any]] = [
    {
        "title": "Python for Everybody",
        "provider": "Coursera",
        "url": "https://www.coursera.org/specializations/python",
        "cost": 0.0,
        "duration_hours": 40.0,
        "difficulty": "beginner",
        "rating": 4.8,
        "skills": ["python", "problem_solving"],
    },
    {
        "title": "SQL for Data Analysis",
        "provider": "Mode",
        "url": "https://mode.com/sql-tutorial/",
        "cost": 0.0,
        "duration_hours": 12.0,
        "difficulty": "beginner",
        "rating": 4.5,
        "skills": ["sql", "data_cleaning"],
    },
    {
        "title": "Excel Skills for Business",
        "provider": "Coursera",
        "url": "https://www.coursera.org/specializations/excel",
        "cost": 0.0,
        "duration_hours": 30.0,
        "difficulty": "beginner",
        "rating": 4.8,
        "skills": ["excel", "data_visualization", "business_analysis"],
    },
    {
        "title": "Power BI Data Analyst",
        "provider": "Microsoft Learn",
        "url": "https://learn.microsoft.com/training/powerplatform/power-bi",
        "cost": 0.0,
        "duration_hours": 22.0,
        "difficulty": "intermediate",
        "rating": 4.6,
        "skills": ["power_bi", "data_visualization", "data_modeling"],
    },
    {
        "title": "Tableau Training Videos",
        "provider": "Tableau",
        "url": "https://www.tableau.com/learn/training",
        "cost": 0.0,
        "duration_hours": 16.0,
        "difficulty": "beginner",
        "rating": 4.5,
        "skills": ["tableau", "data_visualization"],
    },
    {
        "title": "Statistics and Probability",
        "provider": "Khan Academy",
        "url": "https://www.khanacademy.org/math/statistics-probability",
        "cost": 0.0,
        "duration_hours": 24.0,
        "difficulty": "beginner",
        "rating": 4.7,
        "skills": ["statistics", "problem_solving"],
    },
    {
        "title": "Data Cleaning with Python and Pandas",
        "provider": "Kaggle Learn",
        "url": "https://www.kaggle.com/learn/pandas",
        "cost": 0.0,
        "duration_hours": 8.0,
        "difficulty": "beginner",
        "rating": 4.6,
        "skills": ["pandas", "data_cleaning", "python"],
    },
    {
        "title": "Intro to Machine Learning",
        "provider": "Kaggle Learn",
        "url": "https://www.kaggle.com/learn/intro-to-machine-learning",
        "cost": 0.0,
        "duration_hours": 10.0,
        "difficulty": "intermediate",
        "rating": 4.6,
        "skills": ["machine_learning", "scikit_learn", "statistics"],
    },
    {
        "title": "Business Analysis Fundamentals",
        "provider": "IIBA",
        "url": "https://www.iiba.org/business-analysis-blogs/business-analysis-basics/",
        "cost": 0.0,
        "duration_hours": 8.0,
        "difficulty": "beginner",
        "rating": 4.2,
        "skills": ["business_analysis", "requirements_gathering", "stakeholder_management"],
    },
    {
        "title": "Agile with Atlassian Jira",
        "provider": "Coursera",
        "url": "https://www.coursera.org/learn/agile-atlassian-jira",
        "cost": 0.0,
        "duration_hours": 12.0,
        "difficulty": "beginner",
        "rating": 4.7,
        "skills": ["agile", "stakeholder_management"],
    },
    {
        "title": "How to Write a Resume",
        "provider": "Job Bank Canada",
        "url": "https://www.jobbank.gc.ca/findajob/resources/write-good-resume",
        "cost": 0.0,
        "duration_hours": 3.0,
        "difficulty": "beginner",
        "rating": 4.2,
        "skills": ["resume_tailoring", "canadian_labor_market"],
    },
    {
        "title": "Interview Preparation",
        "provider": "Job Bank Canada",
        "url": "https://www.jobbank.gc.ca/findajob/resources/interview",
        "cost": 0.0,
        "duration_hours": 4.0,
        "difficulty": "beginner",
        "rating": 4.2,
        "skills": ["interview_preparation", "communication"],
    },
]


CAPSTONE_ROLE_SKILL_SEED_DATA: dict[str, list[dict[str, Any]]] = {
    "Data Analyst": [
        {"skill": "sql", "importance": 0.95},
        {"skill": "excel", "importance": 0.85},
        {"skill": "python", "importance": 0.8},
        {"skill": "data_cleaning", "importance": 0.9},
        {"skill": "statistics", "importance": 0.8},
        {"skill": "data_visualization", "importance": 0.9},
        {"skill": "power_bi", "importance": 0.75},
        {"skill": "communication", "importance": 0.7},
        {"skill": "kpi_design", "importance": 0.7},
    ],
    "Business Analyst": [
        {"skill": "business_analysis", "importance": 0.95},
        {"skill": "requirements_gathering", "importance": 0.9},
        {"skill": "stakeholder_management", "importance": 0.85},
        {"skill": "excel", "importance": 0.8},
        {"skill": "sql", "importance": 0.7},
        {"skill": "kpi_design", "importance": 0.8},
        {"skill": "communication", "importance": 0.9},
        {"skill": "agile", "importance": 0.7},
        {"skill": "problem_solving", "importance": 0.75},
    ],
    "Junior Data Scientist": [
        {"skill": "python", "importance": 0.95},
        {"skill": "statistics", "importance": 0.9},
        {"skill": "machine_learning", "importance": 0.9},
        {"skill": "pandas", "importance": 0.85},
        {"skill": "numpy", "importance": 0.8},
        {"skill": "scikit_learn", "importance": 0.8},
        {"skill": "sql", "importance": 0.75},
        {"skill": "data_cleaning", "importance": 0.85},
        {"skill": "github", "importance": 0.65},
        {"skill": "communication", "importance": 0.65},
    ],
}


async def seed_capstone_analytics_minimum(session: AsyncSession) -> dict[str, int]:
    """Seed a small analytical catalog for local P1 gap-analysis experiments."""

    skill_names = [skill["name"] for skill in CAPSTONE_SKILL_SEED_DATA]
    existing_skills_result = await session.execute(
        select(SkillModel).where(SkillModel.normalized_name.in_(skill_names))
    )
    skills_by_name = {skill.normalized_name: skill for skill in existing_skills_result.scalars().all()}

    created_skills = 0
    for skill_data in CAPSTONE_SKILL_SEED_DATA:
        if skill_data["name"] in skills_by_name:
            continue
        skill = SkillModel(
            normalized_name=skill_data["name"],
            display_name=skill_data["display"],
            category=skill_data["category"],
            source="capstone_seed",
        )
        session.add(skill)
        skills_by_name[skill.normalized_name] = skill
        created_skills += 1

    await session.flush()

    alias_values = [alias for skill in CAPSTONE_SKILL_SEED_DATA for alias in skill["aliases"]]
    existing_aliases_result = await session.execute(
        select(SkillAliasModel.alias).where(SkillAliasModel.alias.in_(alias_values))
    )
    existing_aliases = set(existing_aliases_result.scalars().all())

    created_aliases = 0
    for skill_data in CAPSTONE_SKILL_SEED_DATA:
        skill = skills_by_name[skill_data["name"]]
        for alias in skill_data["aliases"]:
            if alias in existing_aliases:
                continue
            session.add(SkillAliasModel(skill_id=skill.id, alias=alias, source="capstone_seed"))
            existing_aliases.add(alias)
            created_aliases += 1

    course_keys = [(course["provider"], course["title"]) for course in CAPSTONE_COURSE_SEED_DATA]
    existing_courses_result = await session.execute(select(CourseModel))
    courses_by_key = {
        (course.provider, course.title): course
        for course in existing_courses_result.scalars().all()
        if (course.provider, course.title) in course_keys
    }

    created_courses = 0
    for course_data in CAPSTONE_COURSE_SEED_DATA:
        key = (course_data["provider"], course_data["title"])
        if key in courses_by_key:
            continue
        course = CourseModel(
            title=course_data["title"],
            provider=course_data["provider"],
            url=course_data["url"],
            cost=course_data["cost"],
            duration_hours=course_data["duration_hours"],
            difficulty=course_data["difficulty"],
            rating=course_data["rating"],
            is_active=True,
        )
        session.add(course)
        courses_by_key[key] = course
        created_courses += 1

    await session.flush()

    created_course_skills = 0
    for course_data in CAPSTONE_COURSE_SEED_DATA:
        course = courses_by_key[(course_data["provider"], course_data["title"])]
        for skill_name in course_data["skills"]:
            skill = skills_by_name[skill_name]
            existing_link_result = await session.execute(
                select(CourseSkillModel).where(
                    CourseSkillModel.course_id == course.id,
                    CourseSkillModel.skill_id == skill.id,
                )
            )
            if existing_link_result.scalar_one_or_none():
                continue
            session.add(
                CourseSkillModel(
                    course_id=course.id,
                    skill_id=skill.id,
                    coverage_score=0.85,
                    is_prerequisite=False,
                    evidence_text="Mapped from capstone seed catalog.",
                )
            )
            created_course_skills += 1

    created_role_skills = await seed_capstone_role_skill_requirements(session, commit=False)

    await session.commit()

    return {
        "skills": created_skills,
        "aliases": created_aliases,
        "courses": created_courses,
        "course_skills": created_course_skills,
        "role_skills": created_role_skills,
    }


async def seed_capstone_role_skill_requirements(session: AsyncSession, *, commit: bool = True) -> int:
    role_skill_names = {
        requirement["skill"]
        for requirements in CAPSTONE_ROLE_SKILL_SEED_DATA.values()
        for requirement in requirements
    }
    skills_result = await session.execute(
        select(SkillModel).where(SkillModel.normalized_name.in_(role_skill_names))
    )
    skills_by_name = {skill.normalized_name: skill for skill in skills_result.scalars().all()}

    created_role_skills = 0
    for target_role, requirements in CAPSTONE_ROLE_SKILL_SEED_DATA.items():
        for requirement in requirements:
            skill = skills_by_name.get(requirement["skill"])
            if skill is None:
                continue

            existing_result = await session.execute(
                select(JobSkillModel).where(
                    JobSkillModel.job_posting_id.is_(None),
                    JobSkillModel.target_role == target_role,
                    JobSkillModel.skill_id == skill.id,
                    JobSkillModel.extraction_method == "role_seed",
                )
            )
            if existing_result.scalar_one_or_none():
                continue

            session.add(
                JobSkillModel(
                    job_posting_id=None,
                    target_role=target_role,
                    skill_id=skill.id,
                    importance_score=requirement["importance"],
                    extraction_method="role_seed",
                    evidence_text=f"{skill.display_name} is part of the {target_role} seed profile.",
                )
            )
            created_role_skills += 1

    if commit:
        await session.commit()
    return created_role_skills
