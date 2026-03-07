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
        "estimated_duration_minutes": 110,
        "modules": [
            {
                "title": "Resume Foundations",
                "description": "Understand structure and recruiter expectations.",
                "lessons": [
                    (
                        "What recruiters scan in 15 seconds",
                        "video_url",
                        "https://youtu.be/veFlfYjRo1Y\nLearn exactly what recruiters prioritize in the first 15 seconds of your resume review.",
                        8,
                    ),
                    (
                        "ATS-friendly formatting",
                        "video_url",
                        "https://youtu.be/6HPs3i2Nth0\nApply ATS-friendly formatting rules to keep your resume readable by both software and recruiters.",
                        8,
                    ),
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
            {
                "title": "Final Resume Challenge",
                "description": "Submit your improved resume once you complete the previous lessons.",
                "lessons": [
                    (
                        "Upload your final resume for AI review",
                        "resume_upload",
                        "Upload your updated resume based on everything learned in this course. In the next phase we will analyze it, score it from 0 to 10, and share targeted feedback if your score is below 8.",
                        10,
                    ),
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
        "estimated_duration_minutes": 92,
        "external_url": "https://www.youtube.com/playlist?list=PLo8NAACn2jVz5cU9BOhKDGtErVGA8ZVsn",
        "modules": [
            {
                "title": "Profile Positioning",
                "lessons": [
                    (
                        "LinkedIn profile picture Hacks: Get more views and job offers!",
                        "video_url",
                        "https://www.youtube.com/watch?v=uNmKhJDQmT4\nLearn profile picture improvements that increase recruiter clicks and profile trust.",
                        7,
                    ),
                    (
                        "FIX Your LinkedIn Banner NOW and Get Noticed!",
                        "video_url",
                        "https://www.youtube.com/watch?v=QQ8btp0n8Bs\nBuild a banner that communicates your value and makes your profile instantly clearer.",
                        6,
                    ),
                    (
                        "Ex-Recruiter Reveals The Best LinkedIn Headline Formula To Land Jobs!",
                        "video_url",
                        "https://www.youtube.com/watch?v=l7e9yBFafXE\nApply a headline formula that boosts discoverability in recruiter searches.",
                        12,
                    ),
                    (
                        "Stop Writing Boring LinkedIn About Sections (Do This Instead)",
                        "video_url",
                        "https://www.youtube.com/watch?v=kJ-MCZcxcFY\nStructure your About section with impact-focused storytelling and clear outcomes.",
                        11,
                    ),
                    (
                        "How I’d Use The LinkedIn Featured Section as a Job Seeker",
                        "video_url",
                        "https://www.youtube.com/watch?v=BMGBO7bo3Ts\nChoose featured content that proves skills, projects, and real-world results.",
                        7,
                    ),
                    (
                        "How to Write the Perfect LinkedIn Experience Section (Recruiter Tips)",
                        "video_url",
                        "https://www.youtube.com/watch?v=sP2Ltn8CyZc\nTurn responsibilities into achievement bullets recruiters can scan in seconds.",
                        12,
                    ),
                ],
            },
            {
                "title": "Engagement Strategy",
                "lessons": [
                    (
                        "The LinkedIn Hack That Boosted My Recruiter Views 5000%",
                        "video_url",
                        "https://www.youtube.com/watch?v=njQQAmzOpsE\nUse profile and activity tactics that increase recruiter visibility at scale.",
                        8,
                    ),
                    (
                        "How to Get Strong LinkedIn Recommendations (That Get Results)",
                        "video_url",
                        "https://www.youtube.com/watch?v=OlREBavotjI\nRequest recommendations with the right prompt so they highlight your strengths.",
                        7,
                    ),
                    (
                        "How to Optimize Your LinkedIn Education Section for Impact",
                        "video_url",
                        "https://www.youtube.com/watch?v=6Bal8gTI0V0\nFormat your education section to support your target role and credibility.",
                        4,
                    ),
                    (
                        "Ex-Recruiter EXPOSES LinkedIn Open to Work Banner HACK",
                        "video_url",
                        "https://www.youtube.com/watch?v=IB45IDhS6SQ\nSet Open to Work strategically to signal intent without weakening positioning.",
                        7,
                    ),
                    (
                        "How to Customize Your LinkedIn URL in Just a Few Clicks",
                        "video_url",
                        "https://www.youtube.com/watch?v=HT5cnjHVQQo\nClean your public profile URL to look more professional and easier to share.",
                        3,
                    ),
                    (
                        "Making Your LinkedIn Profile Recruiter-Ready (Step-by-Step Instructions)",
                        "video_url",
                        "https://www.youtube.com/watch?v=qWk3CMGyXyk\nFollow an end-to-end checklist to make your full profile recruiter-ready.",
                        8,
                    ),
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
    {
        "title": "HackerRank SQL for Beginners to Advanced",
        "description": "Learn SQL step by step with real HackerRank challenges — from beginner to advanced.\nEach video includes the problem explanation, query logic, and the final solution.\nPerfect for anyone starting in data, analytics, or software development.",
        "icon": "🧠",
        "category": "Career",
        "tags": ["LeetCode", "SQL", "Interviews", "HackerRank"],
        "level": "Beginner",
        "estimated_duration_minutes": 90,
        "external_url": "https://www.youtube.com/playlist?list=PLtIxAGlpsx_-dHpnhpOs1HOhi84wyDM2M",
        "modules": [
            {
                "title": "Filtering Fundamentals",
                "description": "Start with basic WHERE conditions and single-table retrieval patterns.",
                "lessons": [
                    (
                        "SQL for Beginners #1 (HackerRank) – Selecting American Cities with Population Over 100,000",
                        "video_url",
                        "https://www.youtube.com/watch?v=npGhyCcU3zE\nLearn how to filter rows with basic numeric conditions using WHERE.",
                        8,
                    ),
                    (
                        "SQL for Beginners #2 (HackerRank)– Query all the NAME of American Cities with population Over 120000",
                        "video_url",
                        "https://www.youtube.com/watch?v=c5_KOVCK-6E\nReturn specific columns while applying stricter population filters.",
                        8,
                    ),
                    (
                        "SQL for Beginners #3 (HackerRank) – Query CITY WITH ID = ID",
                        "video_url",
                        "https://www.youtube.com/watch?v=EpM13lnXlUs\nUse equality-based filters to target exact records by identifier.",
                        8,
                    ),
                    (
                        "SQL for Beginners #8 (HackerRank) – Filter Employees by Salary",
                        "video_url",
                        "https://www.youtube.com/watch?v=RoA1cuQMoVg\nApply salary thresholds to isolate qualified employee rows.",
                        8,
                    ),
                ],
            },
            {
                "title": "String and Pattern Queries",
                "description": "Solve interview questions involving string matching, ordering, and edge cases.",
                "lessons": [
                    (
                        "SQL for Beginners #7 (HackerRank) – Cities Starting with Vow",
                        "video_url",
                        "https://www.youtube.com/watch?v=dnEFgQEgs_Q\nUse string predicates to match city names by first-letter patterns.",
                        8,
                    ),
                    (
                        "SQL for Beginners #6.1 (HackerRank) – Shortest and Largest Cities names",
                        "video_url",
                        "https://www.youtube.com/watch?v=7q7zp1sVDcA\nApproach shortest/largest city name queries using sorting and limits.",
                        8,
                    ),
                    (
                        "SQL for Beginners #6.2  (HackerRank) – Shortest and Largest Cities names",
                        "video_url",
                        "https://www.youtube.com/watch?v=8GyozohXivI\nReview alternate solutions for tie-breaking and lexicographic ordering.",
                        8,
                    ),
                ],
            },
            {
                "title": "Aggregation and Distinct",
                "description": "Practice counts and uniqueness checks common in coding interviews.",
                "lessons": [
                    (
                        "SQL for Beginners #5  (HackerRank) – Count Total and Unique Cities in Station",
                        "video_url",
                        "https://www.youtube.com/watch?v=J6gInrod4zY\nCompare COUNT(*) vs COUNT(DISTINCT ...) in real interview prompts.",
                        8,
                    ),
                    (
                        "SQL: Format Names + Count Occupations (Easy)",
                        "video_url",
                        "https://www.youtube.com/watch?v=9YDvzPakhn0\nCombine formatting and grouped counts to build interview-ready query output.",
                        9,
                    ),
                ],
            },
            {
                "title": "Set Logic and IDs",
                "description": "Handle numeric ID constraints and deduplication patterns cleanly.",
                "lessons": [
                    (
                        "SQL for Beginners #4 (HackerRank) – CITY Names with Even ID Num",
                        "video_url",
                        "https://www.youtube.com/watch?v=6ce56x6DPeM\nFilter by parity and avoid duplicates when selecting by ID patterns.",
                        8,
                    ),
                ],
            },
        ],
    },
    {
        "title": "LeetCode Interview Prep: Arrays, Strings, and Hashing",
        "description": "LeetCode-style interview walkthroughs focused on core Python problem-solving patterns.",
        "icon": "🧩",
        "category": "Career",
        "tags": ["LeetCode", "Interviews", "Arrays", "Hashing", "Python"],
        "level": "Beginner",
        "estimated_duration_minutes": 60,
        "external_url": "https://www.youtube.com/playlist?list=PLtIxAGlpsx_9nHZQ2Wk_4N7il7ZJT_qY8",
        "modules": [
            {
                "title": "Arrays and Hashing",
                "description": "Build fast lookup and frequency-map intuition for classic interview questions.",
                "lessons": [
                    (
                        "Contains Duplicate | 3 Easy Python Solution",
                        "video_url",
                        "https://www.youtube.com/watch?v=IqvwVIZi7UM\nLearn three clean approaches to detect duplicates efficiently in Python.",
                        8,
                    ),
                    (
                        "Group Anagrams  Python Solution",
                        "video_url",
                        "https://www.youtube.com/watch?v=8WAaRE1XauI\nUse hash-map signatures to group anagrams with optimal runtime.",
                        8,
                    ),
                    (
                        "Top K Frequent Elements – Fast Python Solution",
                        "video_url",
                        "https://www.youtube.com/watch?v=m38aZeVH6p8\nSolve top-k frequency queries using counting patterns and efficient selection.",
                        8,
                    ),
                    (
                        "Longest Consecutive Sequence - Python solution",
                        "video_url",
                        "https://www.youtube.com/watch?v=AGRcmT8SnFw\nApply set-based logic to reach linear-time sequence detection.",
                        8,
                    ),
                ],
            },
            {
                "title": "Strings and Two Pointers",
                "description": "Practice robust string validation with readable pointer-based logic.",
                "lessons": [
                    (
                        "Solve Valid Palindrome in Python - 3 Solutions",
                        "video_url",
                        "https://www.youtube.com/watch?v=gFFDJ_fI_2A\nCompare multiple palindrome strategies and choose the right tradeoff in interviews.",
                        8,
                    ),
                ],
            },
            {
                "title": "Interview Career and Coding Communication",
                "description": "Supplement technical prep with communication and career execution habits.",
                "lessons": [
                    (
                        "How I Made Job Fairs Finally Work for Me",
                        "video_url",
                        "https://www.youtube.com/watch?v=7xxsvrAnW24\nPrepare stronger networking and outreach tactics for recruiting events.",
                        8,
                    ),
                    (
                        "Naming Things in Code",
                        "video_url",
                        "https://www.youtube.com/watch?v=-J3wNP6u5YU\nImprove code clarity with practical naming conventions interviewers appreciate.",
                        8,
                    ),
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
                    title, content_type, content = lesson_data[:3]
                    reading_time_minutes = lesson_data[3] if len(lesson_data) > 3 else 8
                    lesson = ResourceLessonModel(
                        module_id=module.id,
                        title=title,
                        position=lesson_index,
                        content_type=content_type,
                        content=content,
                        reading_time_minutes=reading_time_minutes,
                    )
                    session.add(lesson)

        await session.commit()
        print("Seeded resources successfully.")


if __name__ == "__main__":
    asyncio.run(seed_resources())
