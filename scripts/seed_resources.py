import asyncio
import sys
from pathlib import Path

from sqlalchemy import select

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from app.db import async_session
from app.models.resourceModel import ResourceModel, ResourceModuleModel, ResourceLessonModel


SEED_RESOURCES = [
    {
        "title": "Resume Templates",
        "description": "ATS-friendly resume templates and writing playbooks for student and junior roles.",
        "icon": "📄",
        "category": "Career",
        "tags": ["Resume", "ATS", "Career"],
        "level": "Beginner",
        "estimated_duration_minutes": 95,
        "modules": [
            {
                "title": "Resume Foundations",
                "description": "Understand structure and recruiter expectations.",
                "lessons": [
                    ("What recruiters scan in 15 seconds", "text", "Recruiters first scan title, skills, and impact. Keep key achievements at the top."),
                    ("ATS-friendly formatting", "text", "Use a single column, simple headings, and standard fonts."),
                    ("Strong bullet writing", "text", "Use action + context + measurable impact in each bullet."),
                ],
            },
            {
                "title": "Section-by-Section Builder",
                "description": "Craft each section with examples.",
                "lessons": [
                    ("Headline and summary", "text", "Write a 2-line summary with domain, strengths, and role target."),
                    ("Experience and projects", "text", "Show scope, tools, and outcomes for each role/project."),
                    ("Skills and certifications", "text", "Group technical, analytical, and soft skills clearly."),
                ],
            },
        ],
    },
    {
        "title": "LinkedIn Optimization",
        "description": "Optimize profile sections to improve discoverability and outreach responses.",
        "icon": "💼",
        "category": "Professional",
        "tags": ["LinkedIn", "Networking", "Brand"],
        "level": "Intermediate",
        "estimated_duration_minutes": 80,
        "external_url": "https://www.linkedin.com/",
        "modules": [
            {
                "title": "Profile Positioning",
                "lessons": [
                    ("High-converting headline", "text", "Use role + skills + value proposition."),
                    ("About section framework", "text", "Present your story, strengths, and call-to-action."),
                    ("Featured section examples", "text", "Pin your strongest projects, CV, and portfolio links."),
                ],
            },
            {
                "title": "Engagement Strategy",
                "lessons": [
                    ("Connection request templates", "text", "Personalize each note with context and intent."),
                    ("Weekly posting cadence", "text", "Share one insight, one project, and one reflection weekly."),
                    ("Networking follow-ups", "text", "Use value-driven follow-ups, not generic asks."),
                ],
            },
        ],
    },
    {
        "title": "Interview Preparation",
        "description": "Practice behavioral and technical interviews with repeatable frameworks.",
        "icon": "🎯",
        "category": "Career",
        "tags": ["Interview", "STAR", "Practice"],
        "level": "Beginner",
        "estimated_duration_minutes": 120,
        "modules": [
            {
                "title": "Behavioral Interview Core",
                "lessons": [
                    ("STAR method refresher", "text", "Structure every answer: Situation, Task, Action, Result."),
                    ("Leadership and teamwork prompts", "text", "Prepare 2 stories showing collaboration and ownership."),
                    ("Failure and conflict questions", "text", "Focus on reflection, learning, and concrete outcomes."),
                ],
            },
            {
                "title": "Technical Interview Core",
                "lessons": [
                    ("Problem-solving walkthrough", "text", "Clarify assumptions before coding and narrate decisions."),
                    ("Common SQL checks", "text", "Review joins, aggregations, and data quality checks."),
                    ("Mock interview checklist", "text", "Run timed mocks and capture feedback after each round."),
                ],
            },
        ],
    },
    {
        "title": "Portfolio Checklist",
        "description": "A practical checklist to present projects with impact and clear storytelling.",
        "icon": "🎨",
        "category": "Career",
        "tags": ["Portfolio", "Projects", "Showcase"],
        "level": "Beginner",
        "estimated_duration_minutes": 70,
        "modules": [
            {
                "title": "Portfolio Structure",
                "lessons": [
                    ("Homepage essentials", "text", "Introduce yourself, your focus area, and top projects."),
                    ("Project detail template", "text", "Use problem, approach, stack, and outcomes."),
                    ("Design and readability", "text", "Keep spacing, typography, and hierarchy consistent."),
                ],
            },
            {
                "title": "Proof of Impact",
                "lessons": [
                    ("Metrics and outcomes", "text", "Add measurable impact to every project card."),
                    ("Screenshots and demos", "text", "Include visuals plus short context captions."),
                    ("Call-to-action", "text", "Make contact links and resume download obvious."),
                ],
            },
        ],
    },
    {
        "title": "Online Courses",
        "description": "How to select and complete online courses that align with your goals.",
        "icon": "📚",
        "category": "Learning",
        "tags": ["Courses", "Learning", "Planning"],
        "level": "Intermediate",
        "estimated_duration_minutes": 140,
        "modules": [
            {
                "title": "Course Selection",
                "lessons": [
                    ("Define your target skill", "text", "Map roles to required skills before enrolling."),
                    ("Evaluate syllabus quality", "text", "Check outcomes, projects, and recency of content."),
                    ("Avoid tutorial overload", "text", "Choose fewer, deeper courses with projects."),
                ],
            },
            {
                "title": "Execution Plan",
                "lessons": [
                    ("Study schedule template", "text", "Block fixed weekly study sessions."),
                    ("Retention techniques", "text", "Summarize concepts and teach back key ideas."),
                    ("Capstone application", "text", "Build one project per course to prove mastery."),
                ],
            },
        ],
    },
    {
        "title": "Networking Guide",
        "description": "Build meaningful professional relationships online and offline.",
        "icon": "🤝",
        "category": "Professional",
        "tags": ["Networking", "Community", "Mentors"],
        "level": "Beginner",
        "estimated_duration_minutes": 85,
        "modules": [
            {
                "title": "Networking Fundamentals",
                "lessons": [
                    ("Networking mindset", "text", "Focus on value and relationships, not transactions."),
                    ("Where to meet professionals", "text", "Use communities, events, and alumni channels."),
                    ("Conversation starters", "text", "Prepare concise intros and context-based questions."),
                ],
            },
            {
                "title": "Follow-up and Relationship Building",
                "lessons": [
                    ("Post-meeting follow-up", "text", "Send a short thank-you and one specific takeaway."),
                    ("Quarterly check-ins", "text", "Share progress updates and useful resources."),
                    ("Give before you ask", "text", "Offer support, links, or introductions where possible."),
                ],
            },
        ],
    },
    {
        "title": "Salary Negotiation",
        "description": "Negotiation frameworks to improve compensation outcomes with confidence.",
        "icon": "💰",
        "category": "Career",
        "tags": ["Salary", "Negotiation", "Compensation"],
        "level": "Advanced",
        "estimated_duration_minutes": 65,
        "modules": [
            {
                "title": "Preparation",
                "lessons": [
                    ("Market salary research", "text", "Collect reliable salary ranges and role benchmarks."),
                    ("Your leverage inventory", "text", "List skills, impact, and unique differentiators."),
                    ("Target and walk-away points", "text", "Define ideal, acceptable, and minimum outcomes."),
                ],
            },
            {
                "title": "Negotiation Execution",
                "lessons": [
                    ("Offer response script", "text", "Express excitement and ask for total package review."),
                    ("Counteroffer structure", "text", "Anchor with market data and contribution evidence."),
                    ("Non-salary benefits", "text", "Negotiate remote flexibility, budget, and growth plans."),
                ],
            },
        ],
    },
    {
        "title": "Certifications Guide",
        "description": "Choose certifications that signal skills and support your target role.",
        "icon": "🏆",
        "category": "Learning",
        "tags": ["Certifications", "Credentials", "Career Growth"],
        "level": "Intermediate",
        "estimated_duration_minutes": 110,
        "modules": [
            {
                "title": "Certification Strategy",
                "lessons": [
                    ("When a cert is worth it", "text", "Prioritize certs aligned with role requirements."),
                    ("Budget and ROI", "text", "Estimate cost, prep time, and expected benefit."),
                    ("Build your certification roadmap", "text", "Sequence foundational then specialized certs."),
                ],
            },
            {
                "title": "Exam Preparation",
                "lessons": [
                    ("Study plan by week", "text", "Plan revision cycles and timed practice tests."),
                    ("Practice exam strategy", "text", "Review explanations, not just final score."),
                    ("Showcase your credential", "text", "Add certs to resume, LinkedIn, and portfolio."),
                ],
            },
        ],
    },
]


async def seed_resources() -> None:
    async with async_session() as session:
        for resource_data in SEED_RESOURCES:
            existing = await session.execute(
                select(ResourceModel).where(ResourceModel.title == resource_data["title"])
            )
            if existing.scalar_one_or_none():
                continue

            resource = ResourceModel(
                title=resource_data["title"],
                description=resource_data["description"],
                icon=resource_data.get("icon"),
                category=resource_data["category"],
                tags=resource_data.get("tags"),
                level=resource_data.get("level"),
                estimated_duration_minutes=resource_data.get("estimated_duration_minutes"),
                external_url=resource_data.get("external_url"),
                is_published=True,
            )
            session.add(resource)
            await session.flush()

            for module_index, module_data in enumerate(resource_data["modules"], start=1):
                module = ResourceModuleModel(
                    resource_id=resource.id,
                    title=module_data["title"],
                    position=module_index,
                    description=module_data.get("description"),
                )
                session.add(module)
                await session.flush()

                for lesson_index, lesson_data in enumerate(module_data["lessons"], start=1):
                    title, content_type, content = lesson_data
                    lesson = ResourceLessonModel(
                        module_id=module.id,
                        title=title,
                        position=lesson_index,
                        content_type=content_type,
                        content=content,
                        reading_time_minutes=8,
                    )
                    session.add(lesson)

        await session.commit()
        print("Seeded resources successfully.")


if __name__ == "__main__":
    asyncio.run(seed_resources())
