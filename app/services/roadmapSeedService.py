from __future__ import annotations

import os
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import async_session
from app.models.roadmapModel import RoadmapModel, RoadmapStageModel, StageProjectModel, StageTaskModel, TaskType


ROADMAP_SEED_DATA: list[dict[str, Any]] = [
    {
        "slug": "web-developer",
        "title": "Web Developer",
        "description": "Become a job-ready web developer by mastering frontend, backend, databases, deployment, and portfolio storytelling.",
        "role_target": "Junior Web Developer",
        "difficulty": "Beginner to Intermediate",
        "duration_weeks_min": 24,
        "duration_weeks_max": 36,
        "stages": [
            {
                "title": "Web Foundations",
                "objective": "Build strong fundamentals in semantic HTML, modern CSS, and core web platform concepts.",
                "duration_weeks": 4,
                "tasks": [
                    {
                        "title": "Understand how the web works",
                        "description": "Learn clients vs servers, DNS, HTTP/HTTPS, and what happens when loading a page.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                        "resource_title": "How the Web Works",
                        "resource_url": "https://developer.mozilla.org/en-US/docs/Learn_web_development/Getting_started/Web_standards/How_the_web_works",
                    },
                    {
                        "title": "Write semantic HTML structure",
                        "description": "Use landmarks, heading hierarchy, and reusable section patterns.",
                        "estimated_hours": 6,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Build accessible forms",
                        "description": "Create forms with labels, validation states, and helpful error messaging.",
                        "estimated_hours": 5,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Master CSS cascade and selectors",
                        "description": "Practice specificity, inheritance, and structuring maintainable style layers.",
                        "estimated_hours": 5,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Layout pages with Flexbox and Grid",
                        "description": "Implement common UI layouts and responsive card grids.",
                        "estimated_hours": 8,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Implement responsive breakpoints",
                        "description": "Make pages mobile-first and adapt typography, spacing, and layout across viewports.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Apply accessibility basics",
                        "description": "Add alt text, keyboard focus states, and sufficient color contrast.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                        "resource_title": "WCAG Quick Reference",
                        "resource_url": "https://www.w3.org/WAI/WCAG21/quickref/",
                    },
                    {
                        "title": "Use CSS transitions and simple animation",
                        "description": "Add purposeful motion for hover, focus, and page feedback.",
                        "estimated_hours": 3,
                        "task_type": TaskType.WATCH,
                    },
                    {
                        "title": "Practice Git and GitHub workflow",
                        "description": "Create branches, commits, pull requests, and merge changes cleanly.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Publish a static site",
                        "description": "Deploy a static project with a custom README and production URL.",
                        "estimated_hours": 4,
                        "task_type": TaskType.BUILD,
                    },
                ],
                "project": {
                    "title": "Responsive Landing Page",
                    "brief": "Build an accessible, responsive landing page for a fictional SaaS product with clear hero messaging, feature sections, pricing block, and contact form.",
                    "estimated_hours": 12,
                    "acceptance_criteria": [
                        "Uses semantic HTML5 sections and proper heading hierarchy",
                        "Looks polished on mobile, tablet, and desktop",
                        "Has keyboard-accessible navigation and form controls",
                        "Meets contrast and readability guidelines",
                        "Includes clean folder structure and README",
                        "Published with a shareable live URL",
                    ],
                    "rubric": {
                        "functionality": "All sections render correctly and links/forms behave as expected.",
                        "code_quality": "HTML/CSS are organized, reusable, and easy to maintain.",
                        "UX": "Layout, spacing, typography, and responsive behavior feel intentional.",
                        "documentation": "README explains goals, structure, and setup clearly.",
                        "deployment": "Live site is reachable and stable with no broken assets.",
                    },
                },
            },
            {
                "title": "JavaScript Core",
                "objective": "Gain fluency with JavaScript syntax, DOM APIs, asynchronous programming, and browser storage.",
                "duration_weeks": 6,
                "tasks": [
                    {
                        "title": "Practice JavaScript fundamentals",
                        "description": "Cover variables, types, conditions, loops, and functions with exercises.",
                        "estimated_hours": 6,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Use arrays and objects effectively",
                        "description": "Implement map/filter/reduce and object transformations.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Manipulate the DOM",
                        "description": "Select, create, and update elements while avoiding redundant reflows.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Handle events and forms",
                        "description": "Build event-driven interactions and validation feedback.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Learn async JavaScript",
                        "description": "Master callbacks, promises, async/await, and execution flow.",
                        "estimated_hours": 6,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Fetch data from APIs",
                        "description": "Consume REST APIs, parse JSON, and update the UI reliably.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Implement resilient error handling",
                        "description": "Use try/catch, fallback UI states, and retries for unstable calls.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Persist state with localStorage",
                        "description": "Store user preferences and task state between sessions.",
                        "estimated_hours": 4,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Read and write modular JS",
                        "description": "Split logic into modules and avoid global variable leakage.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                        "resource_title": "ES Modules Guide",
                        "resource_url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules",
                    },
                    {
                        "title": "Debug with browser devtools",
                        "description": "Inspect network calls, set breakpoints, and trace runtime issues.",
                        "estimated_hours": 4,
                        "task_type": TaskType.WATCH,
                    },
                ],
                "project": {
                    "title": "JavaScript Productivity App",
                    "brief": "Build a task manager mini-app with CRUD todos, localStorage persistence, and an API-powered insights widget (e.g., weather/quotes/news).",
                    "estimated_hours": 16,
                    "acceptance_criteria": [
                        "Supports add/edit/delete/complete todo operations",
                        "Persists todo data in localStorage",
                        "Displays data from at least one public API",
                        "Shows loading, success, and error states",
                        "Uses modular JavaScript files",
                        "Includes clear README and project screenshots",
                    ],
                    "rubric": {
                        "functionality": "Todo and API features work smoothly across refreshes.",
                        "code_quality": "Code is modular, readable, and avoids duplicated logic.",
                        "UX": "Interaction states are clear and responsive across devices.",
                        "documentation": "README includes architecture, features, and setup.",
                        "deployment": "Hosted build is stable with working API integration.",
                    },
                },
            },
            {
                "title": "Frontend Framework",
                "objective": "Build production-style interfaces with React, component architecture, state management, and routing.",
                "duration_weeks": 6,
                "tasks": [
                    {
                        "title": "Set up React with modern tooling",
                        "description": "Initialize a React app and understand build/dev scripts.",
                        "estimated_hours": 3,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Build reusable components",
                        "description": "Create composable UI components with clear props contracts.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Manage state with hooks",
                        "description": "Use useState/useMemo/useCallback and avoid unnecessary re-renders.",
                        "estimated_hours": 6,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Handle forms in React",
                        "description": "Implement controlled inputs and validation patterns.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Fetch async data in components",
                        "description": "Use effects and separate data-fetching concerns cleanly.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Implement client-side routing",
                        "description": "Use React Router for nested layouts and dynamic routes.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Add shared app state",
                        "description": "Use Context and reducer patterns for global state.",
                        "estimated_hours": 5,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Style with a scalable approach",
                        "description": "Apply consistent spacing, design tokens, and component states.",
                        "estimated_hours": 4,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Write frontend tests",
                        "description": "Test component behavior and basic integration with user flows.",
                        "estimated_hours": 5,
                        "task_type": TaskType.READ,
                        "resource_title": "React Testing Library",
                        "resource_url": "https://testing-library.com/docs/react-testing-library/intro/",
                    },
                    {
                        "title": "Improve performance basics",
                        "description": "Apply memoization and lazy loading where appropriate.",
                        "estimated_hours": 3,
                        "task_type": TaskType.WATCH,
                    },
                ],
                "project": {
                    "title": "React Search SPA",
                    "brief": "Create a React single-page app with searchable listings, multi-filter controls, detail pages, and route-driven state.",
                    "estimated_hours": 18,
                    "acceptance_criteria": [
                        "Implements search and at least 3 filters",
                        "Supports list and detail pages with routing",
                        "Persists selected filters in URL query params",
                        "Handles loading/error/empty states clearly",
                        "Uses reusable component library in the app",
                        "Includes test coverage for key user flows",
                    ],
                    "rubric": {
                        "functionality": "Search, filters, and routing produce expected results.",
                        "code_quality": "Component boundaries and state flow are clean and maintainable.",
                        "UX": "UI is intuitive, fast, and consistent on mobile and desktop.",
                        "documentation": "README explains architecture decisions and tradeoffs.",
                        "deployment": "SPA is deployed and handles direct route refreshes.",
                    },
                },
            },
            {
                "title": "Backend Foundations",
                "objective": "Design and implement secure backend APIs with FastAPI, REST conventions, and authentication.",
                "duration_weeks": 6,
                "tasks": [
                    {
                        "title": "Review HTTP and REST principles",
                        "description": "Use method semantics, status codes, and idempotency correctly.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                        "resource_title": "MDN HTTP Overview",
                        "resource_url": "https://developer.mozilla.org/en-US/docs/Web/HTTP/Overview",
                    },
                    {
                        "title": "Build FastAPI route modules",
                        "description": "Organize endpoints into routers and structured response models.",
                        "estimated_hours": 6,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Create CRUD operations",
                        "description": "Implement create/read/update/delete endpoints with validation.",
                        "estimated_hours": 7,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Use dependency injection",
                        "description": "Share auth/session dependencies and enforce authorization.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Implement authentication",
                        "description": "Add JWT or secure session login and route protection.",
                        "estimated_hours": 6,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Validate request and response schemas",
                        "description": "Use Pydantic models for strong contracts and cleaner errors.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Handle exceptions consistently",
                        "description": "Create predictable API error responses and error handlers.",
                        "estimated_hours": 3,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Add middleware and security basics",
                        "description": "Configure CORS, trusted hosts, and request logging.",
                        "estimated_hours": 4,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Write backend tests",
                        "description": "Test auth and CRUD behavior with async test clients.",
                        "estimated_hours": 6,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Document APIs with OpenAPI",
                        "description": "Improve endpoint docs with request examples and clear tags.",
                        "estimated_hours": 3,
                        "task_type": TaskType.WATCH,
                    },
                ],
                "project": {
                    "title": "FastAPI CRUD API with Auth",
                    "brief": "Build a production-style API for managing resources (e.g., projects/tasks) with authenticated users, authorization checks, and full CRUD.",
                    "estimated_hours": 20,
                    "acceptance_criteria": [
                        "Supports authenticated CRUD endpoints",
                        "Uses robust schema validation and typed responses",
                        "Enforces user-specific ownership rules",
                        "Includes integration tests for key endpoints",
                        "Returns consistent error payloads",
                        "Provides API documentation and usage examples",
                    ],
                    "rubric": {
                        "functionality": "All CRUD and auth flows work for happy and error paths.",
                        "code_quality": "Service/router boundaries are clean with reusable dependencies.",
                        "UX": "API consumers get predictable responses and clear errors.",
                        "documentation": "OpenAPI docs and README enable quick onboarding.",
                        "deployment": "Service runs in a deployable configuration with env-based settings.",
                    },
                },
            },
            {
                "title": "Databases & Deployment",
                "objective": "Persist data reliably with Postgres, manage schema evolution, containerize services, and deploy full-stack systems.",
                "duration_weeks": 6,
                "tasks": [
                    {
                        "title": "Practice SQL fundamentals",
                        "description": "Write joins, aggregations, subqueries, and indexes for real queries.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Design relational schemas",
                        "description": "Model entities, constraints, and relationships for scalability.",
                        "estimated_hours": 5,
                        "task_type": TaskType.LEARN,
                    },
                    {
                        "title": "Integrate Postgres with SQLAlchemy async",
                        "description": "Configure connection pooling and transactional patterns.",
                        "estimated_hours": 6,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Manage migrations with Alembic",
                        "description": "Generate, review, and apply reversible schema migrations.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Containerize services with Docker",
                        "description": "Build Dockerfiles and local orchestration for frontend/backend/db.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Configure environment-specific settings",
                        "description": "Separate dev/stage/prod secrets and runtime configuration.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                    },
                    {
                        "title": "Deploy Postgres-backed backend",
                        "description": "Provision managed Postgres and apply migrations safely.",
                        "estimated_hours": 5,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Set up CI basics",
                        "description": "Run lint/tests in CI and enforce checks on pull requests.",
                        "estimated_hours": 4,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Serve frontend and API in production",
                        "description": "Configure domains, HTTPS, and reverse proxy routing.",
                        "estimated_hours": 5,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Add monitoring and backup checks",
                        "description": "Track uptime/logs and define backup/restore validation steps.",
                        "estimated_hours": 4,
                        "task_type": TaskType.WATCH,
                    },
                ],
                "project": {
                    "title": "Full-Stack Deployment with CI",
                    "brief": "Deploy a full-stack app (React + FastAPI + Postgres) with environment configs, migrations, and automated CI checks.",
                    "estimated_hours": 22,
                    "acceptance_criteria": [
                        "Frontend and backend are both publicly accessible",
                        "Backend uses managed Postgres and migration workflow",
                        "Docker-based local environment mirrors production setup",
                        "CI pipeline runs tests and basic quality checks",
                        "Environment variables are documented and secure",
                        "Deployment runbook includes rollback steps",
                    ],
                    "rubric": {
                        "functionality": "Deployed app functions end-to-end with persistent data.",
                        "code_quality": "Infrastructure and app code are organized and reproducible.",
                        "UX": "App performance and error handling are acceptable in production.",
                        "documentation": "Runbook and setup docs are complete and actionable.",
                        "deployment": "CI/CD and environment management are reliable and repeatable.",
                    },
                },
            },
            {
                "title": "Portfolio & Job Readiness",
                "objective": "Package your work for hiring success with portfolio storytelling, interview prep, and professional branding.",
                "duration_weeks": 4,
                "tasks": [
                    {
                        "title": "Refactor your top projects",
                        "description": "Polish architecture, remove dead code, and improve README quality.",
                        "estimated_hours": 6,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Write two project case studies",
                        "description": "Document problem, approach, tradeoffs, outcomes, and lessons learned.",
                        "estimated_hours": 6,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Build a portfolio website",
                        "description": "Showcase skills, projects, and clear ways to contact you.",
                        "estimated_hours": 7,
                        "task_type": TaskType.BUILD,
                    },
                    {
                        "title": "Optimize GitHub profile",
                        "description": "Pin strong repositories and improve commit hygiene and docs.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Tailor your resume for web roles",
                        "description": "Align resume bullets to junior web developer job descriptions.",
                        "estimated_hours": 4,
                        "task_type": TaskType.READ,
                    },
                    {
                        "title": "Improve LinkedIn positioning",
                        "description": "Set headline, summary, and project highlights for recruiter search.",
                        "estimated_hours": 3,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Run mock technical interviews",
                        "description": "Practice coding, system understanding, and communication under time pressure.",
                        "estimated_hours": 5,
                        "task_type": TaskType.WATCH,
                    },
                    {
                        "title": "Prepare behavioral interview stories",
                        "description": "Draft STAR responses on ownership, teamwork, and conflict.",
                        "estimated_hours": 4,
                        "task_type": TaskType.PRACTICE,
                    },
                    {
                        "title": "Build outreach and applications pipeline",
                        "description": "Track target companies, referrals, and application follow-up schedule.",
                        "estimated_hours": 4,
                        "task_type": TaskType.BUILD,
                    },
                ],
                "project": {
                    "title": "Portfolio Launch Pack",
                    "brief": "Ship a professional portfolio site with two deep case studies, updated resume, polished GitHub, and an interview-readiness checklist.",
                    "estimated_hours": 18,
                    "acceptance_criteria": [
                        "Portfolio includes about section, skills, and at least 3 projects",
                        "Includes 2 detailed case studies with measurable outcomes",
                        "Provides resume download and working contact links",
                        "GitHub profile is curated with pinned repositories",
                        "Interview checklist covers technical + behavioral preparation",
                        "Portfolio is deployed and mobile-friendly",
                    ],
                    "rubric": {
                        "functionality": "Portfolio content and links are complete and accurate.",
                        "code_quality": "Site code is clean, maintainable, and well-structured.",
                        "UX": "Storytelling and navigation make projects easy to evaluate.",
                        "documentation": "Case studies and README provide clear depth and context.",
                        "deployment": "Portfolio and showcased project demos are live and stable.",
                    },
                },
            },
        ],
    },
    {
        "slug": "data-scientist",
        "title": "Data Scientist",
        "description": "A practical route into data science with analytics, machine learning, and portfolio delivery.",
        "role_target": "Junior Data Scientist",
        "difficulty": "Beginner to Intermediate",
        "duration_weeks_min": 20,
        "duration_weeks_max": 30,
        "stages": [
            {
                "title": "Core Analytics",
                "objective": "Learn Python analytics stack, SQL, statistics, and model basics.",
                "duration_weeks": 8,
                "tasks": [
                    {"title": "Python for data analysis", "description": "Use pandas and NumPy for transformations.", "estimated_hours": 8, "task_type": TaskType.LEARN},
                    {"title": "SQL analytics practice", "description": "Solve joins, windows, and aggregations.", "estimated_hours": 8, "task_type": TaskType.PRACTICE},
                    {"title": "Build first ML pipeline", "description": "Train and evaluate baseline models.", "estimated_hours": 10, "task_type": TaskType.BUILD},
                    {"title": "Communicate findings", "description": "Write insight-focused analysis summaries.", "estimated_hours": 4, "task_type": TaskType.READ},
                ],
                "project": {
                    "title": "Predictive Analytics Mini-Project",
                    "brief": "Build a prediction model with feature engineering and clear business insights.",
                    "estimated_hours": 16,
                    "acceptance_criteria": [
                        "Dataset cleaned and validated",
                        "At least 2 baseline models compared",
                        "Evaluation metrics justified",
                        "Results summarized for non-technical audience",
                    ],
                    "rubric": {
                        "functionality": "Pipeline runs end-to-end and produces reproducible outputs.",
                        "code_quality": "Notebook/code is structured and reusable.",
                        "UX": "Visualizations and narrative are easy to interpret.",
                        "documentation": "Assumptions and methodology are explicit.",
                        "deployment": "Model artifacts and instructions are shareable.",
                    },
                },
            }
        ],
    },
    {
        "slug": "product-manager",
        "title": "Product Manager",
        "description": "Develop product thinking, prioritization, and execution skills to drive product outcomes.",
        "role_target": "Associate Product Manager",
        "difficulty": "Beginner",
        "duration_weeks_min": 16,
        "duration_weeks_max": 24,
        "stages": [
            {
                "title": "Product Thinking",
                "objective": "Learn discovery, prioritization, metrics, and roadmap communication.",
                "duration_weeks": 6,
                "tasks": [
                    {"title": "Define user personas", "description": "Create target persona docs from interview notes.", "estimated_hours": 5, "task_type": TaskType.PRACTICE},
                    {"title": "Write clear problem statements", "description": "Frame user pains and measurable outcomes.", "estimated_hours": 5, "task_type": TaskType.LEARN},
                    {"title": "Prioritize backlog with framework", "description": "Use RICE/MoSCoW for ranked roadmap options.", "estimated_hours": 6, "task_type": TaskType.BUILD},
                    {"title": "Plan experiment metrics", "description": "Define success metrics and test assumptions.", "estimated_hours": 4, "task_type": TaskType.READ},
                ],
                "project": {
                    "title": "Product Strategy Case",
                    "brief": "Prepare a product strategy case with user research summary, prioritized roadmap, and KPI plan.",
                    "estimated_hours": 14,
                    "acceptance_criteria": [
                        "Clear user problem and target segment",
                        "Roadmap prioritized with rationale",
                        "Success metrics and experiment plan defined",
                        "Presentation deck communicates tradeoffs",
                    ],
                    "rubric": {
                        "functionality": "Case includes coherent strategy and execution plan.",
                        "code_quality": "Artifacts are structured and logically rigorous.",
                        "UX": "Narrative is concise and persuasive.",
                        "documentation": "Assumptions and decisions are traceable.",
                        "deployment": "Deliverables are ready for interview presentation.",
                    },
                },
            }
        ],
    },
]


def _env_flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "y", "on"}


async def seed_roadmaps(session: AsyncSession) -> int:
    created_count = 0

    for roadmap_payload in ROADMAP_SEED_DATA:
        existing = await session.execute(
            select(RoadmapModel).where(RoadmapModel.slug == roadmap_payload["slug"])
        )
        if existing.scalar_one_or_none():
            continue

        roadmap = RoadmapModel(
            slug=roadmap_payload["slug"],
            title=roadmap_payload["title"],
            description=roadmap_payload["description"],
            role_target=roadmap_payload["role_target"],
            difficulty=roadmap_payload["difficulty"],
            duration_weeks_min=roadmap_payload["duration_weeks_min"],
            duration_weeks_max=roadmap_payload["duration_weeks_max"],
            is_public=True,
        )
        session.add(roadmap)
        await session.flush()

        for stage_index, stage_payload in enumerate(roadmap_payload["stages"], start=1):
            stage = RoadmapStageModel(
                roadmap_id=roadmap.id,
                order_index=stage_index,
                title=stage_payload["title"],
                objective=stage_payload["objective"],
                duration_weeks=stage_payload["duration_weeks"],
            )
            session.add(stage)
            await session.flush()

            for task_index, task_payload in enumerate(stage_payload["tasks"], start=1):
                session.add(
                    StageTaskModel(
                        stage_id=stage.id,
                        order_index=task_index,
                        title=task_payload["title"],
                        description=task_payload["description"],
                        estimated_hours=task_payload["estimated_hours"],
                        task_type=(
                            task_payload["task_type"].value
                            if hasattr(task_payload["task_type"], "value")
                            else task_payload["task_type"]
                        ),
                        resource_url=task_payload.get("resource_url"),
                        resource_title=task_payload.get("resource_title"),
                    )
                )

            project_payload = stage_payload["project"]
            session.add(
                StageProjectModel(
                    stage_id=stage.id,
                    title=project_payload["title"],
                    brief=project_payload["brief"],
                    acceptance_criteria=project_payload["acceptance_criteria"],
                    rubric=project_payload["rubric"],
                    estimated_hours=project_payload["estimated_hours"],
                )
            )

        created_count += 1

    await session.commit()
    return created_count


async def _roadmaps_table_exists(session: AsyncSession) -> bool:
    dialect = session.get_bind().dialect.name

    if dialect == "postgresql":
        result = await session.execute(text("SELECT to_regclass('public.roadmaps')"))
        return result.scalar_one_or_none() is not None

    if dialect == "sqlite":
        result = await session.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='roadmaps'")
        )
        return result.scalar_one_or_none() is not None

    try:
        await session.execute(text("SELECT 1 FROM roadmaps LIMIT 1"))
        return True
    except Exception:
        return False


async def seed_roadmaps_on_startup_if_dev() -> int:
    env = os.getenv("ENV", "development").strip().lower()
    should_seed = _env_flag("SEED_ROADMAPS_ON_STARTUP", "1" if env == "development" else "0")

    if not should_seed:
        return 0

    try:
        async with async_session() as session:
            if not await _roadmaps_table_exists(session):
                return 0
            return await seed_roadmaps(session)
    except Exception:
        return 0
