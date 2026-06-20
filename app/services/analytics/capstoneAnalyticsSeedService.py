from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.aiUsageModel import AIQuotaGrantModel, AIUsageEventModel  # noqa: F401
from app.models.applicationAnalyticsModel import ApplicationDailyAggregateModel  # noqa: F401
from app.models.applicationAnalyticsModel import ApplicationStatusEventModel  # noqa: F401
from app.models.applicationModel import ApplicationModel  # noqa: F401
from app.models.communityModel import CommunityMemberModel, CommunityModel  # noqa: F401
from app.models.communityPostModel import (  # noqa: F401
    CommunityPostCommentModel,
    CommunityPostLikeModel,
    CommunityPostModel,
)
from app.models.companyModel import Company  # noqa: F401
from app.models.companyRecruiterModel import CompanyRecruiter  # noqa: F401
from app.models.emailNotificationLogModel import EmailNotificationLogModel  # noqa: F401
from app.models.friendshipModel import FriendRequestModel, FriendshipModel  # noqa: F401
from app.models.interviewAvailabilityModel import InterviewAvailabilityModel  # noqa: F401
from app.models.jobAnalysisModel import JobAnalysisModel  # noqa: F401
from app.models.jobPostingModel import JobPosting  # noqa: F401
from app.models.messageModel import ConversationModel, ConversationParticipantModel, MessageModel  # noqa: F401
from app.models.postModel import PostModel  # noqa: F401
from app.models.questionnaireModel import UserQuestionnaire  # noqa: F401
from app.models.resourceModel import ResourceModel  # noqa: F401
from app.models.resourceModel import ResourceLessonModel, ResourceLessonProgressModel, ResourceModuleModel  # noqa: F401
from app.models.resumeCourseEvaluationModel import ResumeCourseEvaluationModel  # noqa: F401
from app.models.resumeEmbeddingsModel import ResumeEmbedding  # noqa: F401
from app.models.resumeModel import ResumeModel  # noqa: F401
from app.models.roadmapModel import (  # noqa: F401
    RoadmapModel,
    RoadmapStageModel,
    StageProjectModel,
    StageTaskModel,
    UserProjectSubmissionModel,
    UserRoadmapModel,
    UserStageProgressModel,
    UserTaskProgressModel,
)
from app.models.skillModel import CourseModel, CourseSkillModel, JobSkillModel, SkillAliasModel, SkillModel
from app.models.userStatsModel import UserStatsModel  # noqa: F401
from app.models.userModel import User  # noqa: F401


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

CAPSTONE_SKILL_SEED_DATA.extend(
    [
        {"name": "java", "display": "Java", "category": "programming", "aliases": ["core java", "java programming"]},
        {"name": "javascript", "display": "JavaScript", "category": "programming", "aliases": ["js", "ecmascript"]},
        {"name": "typescript", "display": "TypeScript", "category": "programming", "aliases": ["ts"]},
        {"name": "html", "display": "HTML", "category": "programming", "aliases": ["html5"]},
        {"name": "css", "display": "CSS", "category": "programming", "aliases": ["css3", "cascading style sheets"]},
        {"name": "react", "display": "React", "category": "frontend", "aliases": ["reactjs", "react.js"]},
        {"name": "angular", "display": "Angular", "category": "frontend", "aliases": ["angularjs"]},
        {"name": "node_js", "display": "Node.js", "category": "backend", "aliases": ["nodejs", "node js"]},
        {"name": "spring_boot", "display": "Spring Boot", "category": "backend", "aliases": ["spring framework", "spring"]},
        {"name": "j2ee", "display": "J2EE", "category": "backend", "aliases": ["java ee", "jee"]},
        {"name": "dotnet", "display": ".NET", "category": "backend", "aliases": ["asp.net", "c# .net"]},
        {"name": "c_sharp", "display": "C#", "category": "programming", "aliases": ["c# programming"]},
        {"name": "c_plus_plus", "display": "C++", "category": "programming", "aliases": ["c++ programming"]},
        {"name": "php", "display": "PHP", "category": "programming", "aliases": ["php development"]},
        {"name": "ruby", "display": "Ruby", "category": "programming", "aliases": ["ruby on rails", "rails"]},
        {"name": "r_programming", "display": "R Programming", "category": "programming", "aliases": ["r programming", "r language"]},
        {"name": "sas", "display": "SAS", "category": "analytics_tools", "aliases": ["sas programming"]},
        {"name": "matlab", "display": "MATLAB", "category": "analytics_tools", "aliases": ["matlab programming"]},
        {"name": "scala", "display": "Scala", "category": "programming", "aliases": ["scala programming"]},
        {"name": "shell_scripting", "display": "Shell Scripting", "category": "technical_tools", "aliases": ["bash scripting", "unix shell"]},
        {"name": "mysql", "display": "MySQL", "category": "database", "aliases": ["mysql database"]},
        {"name": "postgresql", "display": "PostgreSQL", "category": "database", "aliases": ["postgres"]},
        {"name": "oracle_database", "display": "Oracle Database", "category": "database", "aliases": ["oracle sql", "oracle db"]},
        {"name": "sql_server", "display": "SQL Server", "category": "database", "aliases": ["microsoft sql server", "ms sql server"]},
        {"name": "mongodb", "display": "MongoDB", "category": "database", "aliases": ["mongo db"]},
        {"name": "nosql", "display": "NoSQL", "category": "database", "aliases": ["non relational database"]},
        {"name": "hadoop", "display": "Hadoop", "category": "data_engineering", "aliases": ["apache hadoop"]},
        {"name": "spark", "display": "Spark", "category": "data_engineering", "aliases": ["apache spark", "pyspark"]},
        {"name": "hive", "display": "Hive", "category": "data_engineering", "aliases": ["apache hive"]},
        {"name": "snowflake", "display": "Snowflake", "category": "database", "aliases": ["snowflake data warehouse"]},
        {"name": "aws", "display": "AWS", "category": "cloud", "aliases": ["amazon web services"]},
        {"name": "azure", "display": "Azure", "category": "cloud", "aliases": ["microsoft azure"]},
        {"name": "gcp", "display": "Google Cloud", "category": "cloud", "aliases": ["google cloud platform"]},
        {"name": "docker", "display": "Docker", "category": "devops", "aliases": ["docker containers"]},
        {"name": "kubernetes", "display": "Kubernetes", "category": "devops", "aliases": ["k8s"]},
        {"name": "linux", "display": "Linux", "category": "technical_tools", "aliases": ["unix linux", "linux administration"]},
        {"name": "jira", "display": "Jira", "category": "delivery_tools", "aliases": ["atlassian jira"]},
        {"name": "confluence", "display": "Confluence", "category": "delivery_tools", "aliases": ["atlassian confluence"]},
        {"name": "salesforce", "display": "Salesforce", "category": "business_tools", "aliases": ["salesforce crm"]},
        {"name": "servicenow", "display": "ServiceNow", "category": "business_tools", "aliases": ["service now"]},
        {"name": "project_management", "display": "Project Management", "category": "delivery", "aliases": ["program management", "project manager"]},
        {"name": "scrum_master", "display": "Scrum Master", "category": "delivery", "aliases": ["certified scrum master", "csm"]},
        {"name": "product_management", "display": "Product Management", "category": "business", "aliases": ["product manager"]},
        {"name": "user_stories", "display": "User Stories", "category": "business", "aliases": ["user story", "acceptance criteria"]},
        {"name": "process_mapping", "display": "Process Mapping", "category": "business", "aliases": ["process modeling", "workflow mapping"]},
        {"name": "uat", "display": "User Acceptance Testing", "category": "quality", "aliases": ["uat", "user acceptance testing"]},
        {"name": "qa_testing", "display": "QA Testing", "category": "quality", "aliases": ["software testing", "test cases"]},
        {"name": "test_automation", "display": "Test Automation", "category": "quality", "aliases": ["automated testing", "selenium"]},
        {"name": "risk_management", "display": "Risk Management", "category": "business", "aliases": ["risk assessment"]},
        {"name": "budget_management", "display": "Budget Management", "category": "business", "aliases": ["budgeting"]},
        {"name": "vendor_management", "display": "Vendor Management", "category": "business", "aliases": ["vendor relations"]},
        {"name": "change_management", "display": "Change Management", "category": "business", "aliases": ["organizational change"]},
        {"name": "crm", "display": "CRM", "category": "business_tools", "aliases": ["customer relationship management"]},
        {"name": "erp", "display": "ERP", "category": "business_tools", "aliases": ["enterprise resource planning"]},
        {"name": "sap", "display": "SAP", "category": "business_tools", "aliases": ["sap erp"]},
        {"name": "accounting", "display": "Accounting", "category": "finance", "aliases": ["general ledger"]},
        {"name": "financial_analysis", "display": "Financial Analysis", "category": "finance", "aliases": ["financial reporting"]},
        {"name": "bookkeeping", "display": "Bookkeeping", "category": "finance", "aliases": ["book keeping"]},
        {"name": "quickbooks", "display": "QuickBooks", "category": "finance_tools", "aliases": ["quick books"]},
        {"name": "tax_preparation", "display": "Tax Preparation", "category": "finance", "aliases": ["tax filing"]},
        {"name": "accounts_payable", "display": "Accounts Payable", "category": "finance", "aliases": ["ap processing"]},
        {"name": "accounts_receivable", "display": "Accounts Receivable", "category": "finance", "aliases": ["ar processing"]},
        {"name": "auditing", "display": "Auditing", "category": "finance", "aliases": ["audit"]},
        {"name": "forecasting", "display": "Forecasting", "category": "finance", "aliases": ["financial forecasting"]},
        {"name": "digital_marketing", "display": "Digital Marketing", "category": "marketing", "aliases": ["online marketing"]},
        {"name": "seo", "display": "SEO", "category": "marketing", "aliases": ["search engine optimization"]},
        {"name": "social_media_marketing", "display": "Social Media Marketing", "category": "marketing", "aliases": ["social media"]},
        {"name": "market_research", "display": "Market Research", "category": "marketing", "aliases": ["competitive analysis"]},
        {"name": "sales", "display": "Sales", "category": "sales", "aliases": ["business development sales"]},
        {"name": "customer_service", "display": "Customer Service", "category": "service", "aliases": ["client service", "customer support"]},
        {"name": "recruiting", "display": "Recruiting", "category": "hr", "aliases": ["recruitment", "talent acquisition"]},
        {"name": "onboarding", "display": "Onboarding", "category": "hr", "aliases": ["employee onboarding"]},
        {"name": "employee_relations", "display": "Employee Relations", "category": "hr", "aliases": ["hr relations"]},
        {"name": "training_development", "display": "Training and Development", "category": "hr", "aliases": ["learning and development"]},
        {"name": "patient_care", "display": "Patient Care", "category": "healthcare", "aliases": ["clinical care"]},
        {"name": "medical_records", "display": "Medical Records", "category": "healthcare", "aliases": ["electronic medical records", "emr"]},
        {"name": "hipaa", "display": "HIPAA", "category": "healthcare", "aliases": ["hipaa compliance"]},
        {"name": "healthcare_administration", "display": "Healthcare Administration", "category": "healthcare", "aliases": ["health care administration"]},
        {"name": "graphic_design", "display": "Graphic Design", "category": "design", "aliases": ["visual design"]},
        {"name": "adobe_photoshop", "display": "Adobe Photoshop", "category": "design_tools", "aliases": ["photoshop"]},
        {"name": "adobe_illustrator", "display": "Adobe Illustrator", "category": "design_tools", "aliases": ["illustrator"]},
        {"name": "ux_design", "display": "UX Design", "category": "design", "aliases": ["user experience design", "ui ux"]},
        {"name": "autocad", "display": "AutoCAD", "category": "engineering_tools", "aliases": ["auto cad"]},
        {"name": "solidworks", "display": "SolidWorks", "category": "engineering_tools", "aliases": ["solid works"]},
        {"name": "manufacturing", "display": "Manufacturing", "category": "operations", "aliases": ["production planning"]},
        {"name": "quality_assurance", "display": "Quality Assurance", "category": "quality", "aliases": ["quality control"]},
        {"name": "leadership", "display": "Leadership", "category": "soft_skills", "aliases": ["team leadership"]},
        {"name": "teamwork", "display": "Teamwork", "category": "soft_skills", "aliases": ["collaboration"]},
        {"name": "time_management", "display": "Time Management", "category": "soft_skills", "aliases": ["prioritization"]},
        {"name": "negotiation", "display": "Negotiation", "category": "soft_skills", "aliases": ["contract negotiation"]},
        {"name": "strategic_planning", "display": "Strategic Planning", "category": "business", "aliases": ["strategy planning"]},
        {"name": "public_speaking", "display": "Public Speaking", "category": "soft_skills", "aliases": ["public presentations"]},
    ]
)


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
