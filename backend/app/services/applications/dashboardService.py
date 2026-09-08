from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import selectinload
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.models.resourceModel import ResourceModel, ResourceModuleModel
from app.models.userModel import User
from app.models.userStatsModel import UserStatsModel
from app.models.resumeModel import ResumeModel
from app.services.learning.courseProgress import CORE_COURSES, CourseProgressProjector
from typing import Dict, List
from uuid import UUID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    #: The payload keys clients already read. The rows behind them are found by
    #: ``resources.core_code`` through ``CourseProgressProjector``, not by title:
    #: a title is editable, and renaming a course used to zero its progress.
    CORE_RESOURCE_KEYS: tuple[str, ...] = tuple(course.key for course in CORE_COURSES)
    
    @staticmethod
    async def get_company_dashboard(company_id: UUID, session: AsyncSession) -> Dict:
        """
        Get dashboard data for a company including posting/application stats and recent jobs.
        """
        now = datetime.utcnow()

        company_result = await session.execute(select(Company).where(Company.id == company_id))
        company = company_result.scalar_one_or_none()

        active_jobs_result = await session.execute(
            select(func.count(JobPosting.id)).where(
                JobPosting.company_id == company_id,
                JobPosting.is_active.is_(True),
                or_(JobPosting.expires_at.is_(None), JobPosting.expires_at >= now),
            )
        )
        active_job_postings = int(active_jobs_result.scalar_one() or 0)

        application_stats_result = await session.execute(
            select(
                func.count(ApplicationModel.id),
                func.sum(
                    case(
                        (ApplicationModel.status == ApplicationStatus.INTERVIEW, 1),
                        else_=0,
                    )
                ),
                func.sum(
                    case(
                        (ApplicationModel.status == ApplicationStatus.IN_REVIEW, 1),
                        else_=0,
                    )
                ),
            ).where(ApplicationModel.company_id == company_id)
        )
        total_applications, interviews_scheduled, shortlisted = application_stats_result.one()

        recent_jobs_result = await session.execute(
            select(
                JobPosting.id,
                JobPosting.title,
                JobPosting.location,
                JobPosting.job_type,
                JobPosting.is_active,
                JobPosting.created_at,
                JobPosting.expires_at,
                func.count(ApplicationModel.id).label("application_count"),
            )
            .outerjoin(ApplicationModel, ApplicationModel.job_posting_id == JobPosting.id)
            .where(JobPosting.company_id == company_id)
            .group_by(
                JobPosting.id,
                JobPosting.title,
                JobPosting.location,
                JobPosting.job_type,
                JobPosting.is_active,
                JobPosting.created_at,
                JobPosting.expires_at,
            )
            .order_by(JobPosting.created_at.desc())
            .limit(5)
        )

        recent_job_postings = []
        for row in recent_jobs_result.all():
            is_open = row.is_active and (row.expires_at is None or row.expires_at >= now)
            status = "active" if is_open else "closed"
            recent_job_postings.append(
                {
                    "id": str(row.id),
                    "title": row.title,
                    "location": row.location,
                    "job_type": row.job_type,
                    "is_active": bool(row.is_active),
                    "status": status,
                    "status_label": "Active" if status == "active" else "Closed",
                    "created_at": row.created_at.isoformat() if row.created_at else None,
                    "application_count": int(row.application_count or 0),
                }
            )

        return {
            "company": {
                "id": str(company.id) if company else str(company_id),
                "company_name": company.company_name if company else None,
                "industry": company.industry if company else None,
                "location": company.location if company else None,
            },
            "stats": {
                "active_job_postings": active_job_postings,
                "total_applications": int(total_applications or 0),
                "scheduled_interviews": int(interviews_scheduled or 0),
                "shortlisted": int(shortlisted or 0),
            },
            "recent_job_postings": recent_job_postings,
        }

    @staticmethod
    async def get_student_dashboard(user_id: UUID, session: AsyncSession) -> Dict:
        """
        Get complete dashboard data for a student including all stats, progress, and applications
        """
        try:
            logger.info(f"Fetching dashboard data for user: {user_id}")
            
            # Counted in the database. Materialising every application to
            # produce four integers made opening the dashboard cost the user's
            # whole history.
            application_stats = await DashboardService._aggregate_student_application_stats(
                user_id, session
            )

            logger.info(
                "Found %s applications for user %s",
                application_stats["total_applications"],
                user_id,
            )
            
            logger.info(
                "Stats calculated - Total: %s, In Review: %s, Interviews: %s, Offers: %s",
                application_stats["total_applications"],
                application_stats["in_review"],
                application_stats["interviews"],
                application_stats["offers"],
            )
            
            progress_data = await DashboardService._project_student_progress(user_id, session)

            logger.info(f"Progress data: {progress_data}")
            
            # Ordered and limited by the database, not sliced off a full list.
            recent_applications = DashboardService._serialize_recent_applications(
                await DashboardService._fetch_recent_applications(user_id, session),
                include_notes=True,
            )
            
            # Fetch user info to avoid extra client calls
            user_result = await session.execute(select(User).where(User.id == user_id))
            user = user_result.scalar_one_or_none()

            dashboard_data = {
                "user": {
                    "id": str(user.id) if user else str(user_id),
                    "email": user.email if user else None,
                    "nickname": user.nickname if user else None,
                    "first_name": user.first_name if user else None,
                    "last_name": user.last_name if user else None,
                },
                "stats": {
                    "overall_progress": progress_data["overall"],
                    "total_applications": application_stats["total_applications"],
                    "in_review": application_stats["in_review"],
                    "interviews_scheduled": application_stats["interviews"],
                    "offers_received": application_stats["offers"],
                    "applied": application_stats["applied"]
                },
                "progress": {
                    "resume": progress_data["resume"],
                    "linkedin": progress_data["linkedin"],
                    "interview_prep": progress_data["interview_prep"],
                    "portfolio": progress_data["portfolio"]
                },
                "application_breakdown": {
                    "applied": application_stats["applied"],
                    "in_review": application_stats["in_review"],
                    "interviews": application_stats["interviews"],
                    "offers": application_stats["offers"]
                },
                "resource_navigation": await DashboardService._get_core_resource_navigation(user_id, session),
                "recent_applications": recent_applications,
                "resources": [
                    {
                        "title": "ATS-Friendly Resume Templates (Tech)",
                        "url": "#",
                        "icon": "📄"
                    },
                    {
                        "title": "LinkedIn Headline & About Examples (Data/Tech)",
                        "url": "#",
                        "icon": "💼"
                    },
                    {
                        "title": "Interview Question Bank (Behavioral + Technical)",
                        "url": "#",
                        "icon": "🎯"
                    },
                    {
                        "title": "Portfolio Checklist (Projects that recruiters like)",
                        "url": "#",
                        "icon": "🎨"
                    }
                ]
            }
            
            logger.info("Dashboard data compiled successfully")
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Error fetching dashboard data for user {user_id}: {str(e)}", exc_info=True)
            raise
    
    @staticmethod
    async def get_user_dashboard_data(user_id: UUID, session: AsyncSession) -> Dict:
        """
        Get all dashboard data for a user including stats and recent applications
        """
        application_stats = await DashboardService._aggregate_student_application_stats(
            user_id, session
        )

        progress_data = await DashboardService._project_student_progress(user_id, session)

        return {
            "stats": {
                "total_applications": application_stats["total_applications"],
                "in_review": application_stats["in_review"],
                "interviews_scheduled": application_stats["interviews"],
                "offers_received": application_stats["offers"]
            },
            "progress": progress_data,
            "recent_applications": DashboardService._serialize_recent_applications(
                await DashboardService._fetch_recent_applications(user_id, session)
            )
        }

    #: Recent applications shown on the dashboard. Named rather than inlined so
    #: the bound is visible where the payload is built.
    RECENT_APPLICATIONS_LIMIT = 5

    @staticmethod
    def _build_student_application_stats(applications) -> Dict[str, int]:
        """Counts over an in-memory list. Kept for callers that already hold one.

        The dashboard no longer does: see
        :meth:`_aggregate_student_application_stats`, which asks the database
        the same question without loading the rows.
        """
        return {
            "total_applications": len(applications),
            "in_review": sum(1 for app in applications if app.status == ApplicationStatus.IN_REVIEW),
            "interviews": sum(1 for app in applications if app.status == ApplicationStatus.INTERVIEW),
            "offers": sum(1 for app in applications if app.status == ApplicationStatus.OFFER),
            "applied": sum(1 for app in applications if app.status == ApplicationStatus.APPLIED),
        }

    @staticmethod
    async def _aggregate_student_application_stats(
        user_id: UUID, session: AsyncSession
    ) -> Dict[str, int]:
        """The same four counts, as one aggregate query.

        The dashboard used to select every application a user had ever made and
        count them in Python, so the cost of opening it grew with the history —
        and the whole list was resident just to produce four integers and five
        rows. ``COUNT(*) FILTER`` reads the same rows the count needs and
        returns numbers.
        """

        def counted(status: ApplicationStatus):
            return func.count(ApplicationModel.id).filter(ApplicationModel.status == status)

        result = await session.execute(
            select(
                func.count(ApplicationModel.id),
                counted(ApplicationStatus.IN_REVIEW),
                counted(ApplicationStatus.INTERVIEW),
                counted(ApplicationStatus.OFFER),
                counted(ApplicationStatus.APPLIED),
            ).where(ApplicationModel.user_id == user_id)
        )
        total, in_review, interviews, offers, applied = result.one()
        return {
            "total_applications": int(total or 0),
            "in_review": int(in_review or 0),
            "interviews": int(interviews or 0),
            "offers": int(offers or 0),
            "applied": int(applied or 0),
        }

    @staticmethod
    async def _fetch_recent_applications(
        user_id: UUID, session: AsyncSession, *, limit: int | None = None
    ) -> list:
        """The newest applications, ordered and limited by the database.

        ``id`` is the tie-break. Two applications submitted on the same date are
        ordinary — a bulk apply session — and without it the top five would be
        whatever order the rows came back in, so the dashboard could show a
        different five on each refresh.
        """
        page_size = DashboardService.RECENT_APPLICATIONS_LIMIT if limit is None else limit
        result = await session.execute(
            select(ApplicationModel)
            .where(ApplicationModel.user_id == user_id)
            .order_by(ApplicationModel.application_date.desc(), ApplicationModel.id.desc())
            .limit(page_size)
        )
        return list(result.scalars().all())

    @staticmethod
    def _serialize_recent_applications(applications, *, include_notes: bool = False) -> list[Dict]:
        recent_applications = []
        for app in applications:
            payload = {
                "id": str(app.id),
                "job_title": app.job_title,
                "company_id": str(app.company_id),
                "status": app.status.value,
                "application_date": app.application_date.isoformat() if app.application_date else None,
            }
            if include_notes:
                payload["notes"] = app.notes
            recent_applications.append(payload)
        return recent_applications
    
    @staticmethod
    async def _calculate_progress(user_id: UUID, session: AsyncSession) -> Dict:
        """
        Calculate user progress on-the-fly based on different activities
        """
        try:
            logger.info(f"Calculating progress for user: {user_id}")
            
            # Check if user has resumes
            resume_query = select(ResumeModel).where(ResumeModel.user_id == user_id)
            resume_result = await session.execute(resume_query)
            resumes = resume_result.scalars().all()
            
            logger.info(f"User has {len(resumes)} resumes")
            
            # Check if user has completed questionnaires
            from app.models.questionnaireModel import UserQuestionnaire
            questionnaire_query = select(UserQuestionnaire).where(UserQuestionnaire.user_id == user_id)
            questionnaire_result = await session.execute(questionnaire_query)
            questionnaires = questionnaire_result.scalars().all()
            
            logger.info(f"User has {len(questionnaires)} questionnaires")
            
            # Calculate progress percentages
            resume_progress = 65 if resumes else 0
            
            # LinkedIn progress - based on questionnaire completion
            linkedin_progress = 40 if questionnaires else 0
            
            # Interview prep - based on resources accessed or completed
            interview_prep_progress = 25  # Placeholder - can be enhanced later
            
            # Portfolio - can be tracked similarly
            portfolio_progress = 0  # Placeholder
            
            # Overall progress
            overall_progress = (resume_progress + linkedin_progress + interview_prep_progress + portfolio_progress) / 4
            
            progress = {
                "resume": resume_progress,
                "linkedin": linkedin_progress,
                "interview_prep": interview_prep_progress,
                "portfolio": portfolio_progress,
                "overall": round(overall_progress, 1)
            }
            
            logger.info(f"Progress calculated: {progress}")
            return progress
            
        except Exception as e:
            logger.error(f"Error calculating progress for user {user_id}: {str(e)}", exc_info=True)
            raise

    @staticmethod
    async def _project_student_progress(user_id: UUID, session: AsyncSession) -> Dict[str, int | float]:
        """The progress a student is shown, projected from facts.

        ``resource_lesson_progress`` rows and approved resume audits are the
        facts; this is a projection of them and the course page projects the
        same ones, so both screens agree by construction. ``user_stats`` is a
        legacy cache: it is read only when no core course has any content — a
        deployment whose courses were never seeded — and it is never written
        here, because a GET that writes turns every page view into a write.
        """
        projector = CourseProgressProjector(session)
        course_progress = await projector.core_course_progress(user_id)

        if course_progress:
            progress_data = {
                "resume": course_progress.get("resume", 0),
                "linkedin": course_progress.get("linkedin", 0),
                "interview_prep": course_progress.get("interview_prep", 0),
                "portfolio": 0,
            }
        else:
            progress_data = await DashboardService._legacy_progress_fallback(user_id, session)

        progress_data["overall"] = round(
            (progress_data["resume"] + progress_data["linkedin"] + progress_data["interview_prep"]) / 3,
            1,
        )
        return progress_data

    @staticmethod
    async def _legacy_progress_fallback(user_id: UUID, session: AsyncSession) -> Dict[str, int]:
        """The pre-course numbers, read but never written.

        Kept because removing it would drop a deployment without seeded courses
        from its stored percentages to a confident 0%, which is a different
        change from the one this task makes. The stored row wins when it exists;
        otherwise the old activity heuristic is computed in memory and
        discarded. ``user_stats`` rows are no longer created on a read.
        """
        result = await session.execute(select(UserStatsModel).where(UserStatsModel.user_id == user_id))
        stats = result.scalar_one_or_none()
        if stats:
            return {
                "resume": stats.resume_progress,
                "linkedin": stats.linkedin_progress,
                "interview_prep": stats.interview_progress,
                "portfolio": 0,
            }

        heuristic = await DashboardService._calculate_progress(user_id, session)
        return {
            "resume": heuristic["resume"],
            "linkedin": heuristic["linkedin"],
            "interview_prep": heuristic["interview_prep"],
            "portfolio": heuristic["portfolio"],
        }

    @staticmethod
    async def _get_core_resource_progress(user_id: UUID, session: AsyncSession) -> Dict[str, int]:
        """Percentage per core course, from the shared projector.

        Was raw SQL that counted progress rows keyed on the course title. It
        disagreed with the course page in two ways: a ``resume_upload`` lesson
        completed by an approved audit was invisible to it, and an admin
        renaming a course silently zeroed the number.
        """
        try:
            return await CourseProgressProjector(session).core_course_progress(user_id)
        except Exception:
            # Same shape of resilience the raw SQL had: a dashboard must still
            # render when the resources tables are mid-rollout.
            logger.exception("Core course progress unavailable for user %s", user_id)
            return {}

    @staticmethod
    async def _get_core_resource_navigation(user_id: UUID, session: AsyncSession) -> Dict[str, str]:
        """Deep link to the next unfinished lesson of each core course.

        Resolved by ``core_code`` and completed through the shared projector, so
        the link lands on the same lesson the course page shows as next — a
        lesson finished by an approved audit is not offered again here.
        """
        navigation = {key: "/resources" for key in DashboardService.CORE_RESOURCE_KEYS}
        projector = CourseProgressProjector(session)

        try:
            resolved = await projector.resolve_core_courses()
            if not resolved:
                return navigation

            resources_result = await session.execute(
                select(ResourceModel)
                .where(
                    ResourceModel.id.in_(list(resolved.values())),
                    ResourceModel.is_published.is_(True),
                    ResourceModel.is_locked.is_(False),
                )
                .options(selectinload(ResourceModel.modules).selectinload(ResourceModuleModel.lessons))
            )
            resources = {resource.id: resource for resource in resources_result.scalars().all()}
            if not resources:
                return navigation

            completed = await projector.completed_lesson_ids(
                user_id=user_id, resource_ids=list(resources.keys())
            )
        except Exception:
            logger.exception("Core course navigation unavailable for user %s", user_id)
            return navigation

        for key, resource_id in resolved.items():
            resource = resources.get(resource_id)
            if not resource:
                continue

            ordered_lesson_ids = []
            for module in sorted(resource.modules, key=lambda current: current.position):
                ordered_lesson_ids.extend(
                    lesson.id for lesson in sorted(module.lessons, key=lambda current: current.position)
                )

            completed_ids = completed.get(resource_id, set())
            target_lesson_id = next(
                (lesson_id for lesson_id in ordered_lesson_ids if lesson_id not in completed_ids),
                None,
            )
            # Everything done: land on the last lesson rather than nowhere.
            if target_lesson_id is None and ordered_lesson_ids:
                target_lesson_id = ordered_lesson_ids[-1]

            if target_lesson_id:
                navigation[key] = f"/resources/{resource.id}?lesson={target_lesson_id}"
            else:
                navigation[key] = f"/resources/{resource.id}"

        return navigation

    @staticmethod
    async def get_application_by_status(user_id: UUID, status: ApplicationStatus, session: AsyncSession) -> List[ApplicationModel]:
        """
        Get all applications filtered by status
        """
        query = select(ApplicationModel).where(
            ApplicationModel.user_id == user_id,
            ApplicationModel.status == status
        )
        result = await session.execute(query)
        return result.scalars().all()
