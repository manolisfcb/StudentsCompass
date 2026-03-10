from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import bindparam, case, func, or_, select, text
from sqlalchemy.orm import selectinload
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.companyModel import Company
from app.models.jobPostingModel import JobPosting
from app.models.resourceModel import (
    ResourceLessonProgressModel,
    ResourceModel,
    ResourceModuleModel,
)
from app.models.userModel import User
from app.models.userStatsModel import UserStatsModel
from app.models.resumeModel import ResumeModel
from typing import Dict, List
from uuid import UUID
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    CORE_RESOURCE_TITLES = {
        "resume": "Resume Templates",
        "linkedin": "LinkedIn Optimization",
        "interview_prep": "Interview Preparation",
    }
    
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
            
            # Get all user applications
            applications_query = select(ApplicationModel).where(
                ApplicationModel.user_id == user_id
            ).order_by(ApplicationModel.application_date.desc())
            result = await session.execute(applications_query)
            applications = result.scalars().all()
            
            logger.info(f"Found {len(applications)} applications for user {user_id}")
            
            # Calculate stats
            total_applications = len(applications)
            in_review = sum(1 for app in applications if app.status == ApplicationStatus.IN_REVIEW)
            interviews = sum(1 for app in applications if app.status == ApplicationStatus.INTERVIEW)
            offers = sum(1 for app in applications if app.status == ApplicationStatus.OFFER)
            applied = sum(1 for app in applications if app.status == ApplicationStatus.APPLIED)
            
            logger.info(f"Stats calculated - Total: {total_applications}, In Review: {in_review}, Interviews: {interviews}, Offers: {offers}")
            
            # Get or create user stats (authoritative progress values)
            user_stats = await DashboardService._get_or_create_user_stats(user_id, session)
            user_stats = await DashboardService._sync_user_stats_with_resource_progress(user_id, session, user_stats)

            progress_data = {
                "resume": user_stats.resume_progress,
                "linkedin": user_stats.linkedin_progress,
                "interview_prep": user_stats.interview_progress,
                "portfolio": 0,
            }

            overall_progress = round(
                (progress_data["resume"] + progress_data["linkedin"] + progress_data["interview_prep"]) / 3,
                1,
            )
            progress_data["overall"] = overall_progress

            logger.info(f"Progress data: {progress_data}")
            
            # Get recent applications with company info
            recent_applications = []
            for app in applications[:5]:  # Last 5 applications
                recent_applications.append({
                    "id": str(app.id),
                    "job_title": app.job_title,
                    "company_id": str(app.company_id),
                    "status": app.status.value,
                    "application_date": app.application_date.isoformat() if app.application_date else None,
                    "notes": app.notes
                })
            
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
                    "total_applications": total_applications,
                    "in_review": in_review,
                    "interviews_scheduled": interviews,
                    "offers_received": offers,
                    "applied": applied
                },
                "progress": {
                    "resume": progress_data["resume"],
                    "linkedin": progress_data["linkedin"],
                    "interview_prep": progress_data["interview_prep"],
                    "portfolio": progress_data["portfolio"]
                },
                "application_breakdown": {
                    "applied": applied,
                    "in_review": in_review,
                    "interviews": interviews,
                    "offers": offers
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
        # Get all user applications
        applications_query = select(ApplicationModel).where(
            ApplicationModel.user_id == user_id
        )
        result = await session.execute(applications_query)
        applications = result.scalars().all()
        
        # Calculate stats on-the-fly
        total_applications = len(applications)
        
        in_review = sum(1 for app in applications if app.status == ApplicationStatus.IN_REVIEW)
        interviews = sum(1 for app in applications if app.status == ApplicationStatus.INTERVIEW)
        offers = sum(1 for app in applications if app.status == ApplicationStatus.OFFER)
        
        # Use saved stats as authoritative progress values
        user_stats = await DashboardService._get_or_create_user_stats(user_id, session)
        user_stats = await DashboardService._sync_user_stats_with_resource_progress(user_id, session, user_stats)
        progress_data = {
            "resume": user_stats.resume_progress,
            "linkedin": user_stats.linkedin_progress,
            "interview_prep": user_stats.interview_progress,
            "portfolio": 0,
            "overall": round(
                (user_stats.resume_progress + user_stats.linkedin_progress + user_stats.interview_progress) / 3,
                1,
            ),
        }
        
        return {
            "stats": {
                "total_applications": total_applications,
                "in_review": in_review,
                "interviews_scheduled": interviews,
                "offers_received": offers
            },
            "progress": progress_data,
            "recent_applications": [
                {
                    "id": str(app.id),
                    "job_title": app.job_title,
                    "company_id": str(app.company_id),
                    "status": app.status.value,
                    "application_date": app.application_date.isoformat() if app.application_date else None
                }
                for app in sorted(applications, key=lambda x: x.application_date, reverse=True)[:5]
            ]
        }
    
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
    async def _get_or_create_user_stats(user_id: UUID, session: AsyncSession) -> UserStatsModel:
        """Fetch user stats or create defaults using activity-based progress."""
        result = await session.execute(select(UserStatsModel).where(UserStatsModel.user_id == user_id))
        stats = result.scalar_one_or_none()

        if stats:
            return stats

        progress = await DashboardService._calculate_progress(user_id, session)
        stats = UserStatsModel(
            user_id=user_id,
            resume_progress=progress["resume"],
            linkedin_progress=progress["linkedin"],
            interview_progress=progress["interview_prep"],
        )
        session.add(stats)
        await session.commit()
        await session.refresh(stats)
        return stats

    @staticmethod
    def _percent(completed: int, total: int) -> int:
        if total <= 0:
            return 0
        return round((completed / total) * 100)

    @staticmethod
    async def _get_core_resource_progress(user_id: UUID, session: AsyncSession) -> Dict[str, int]:
        title_to_key = {title: key for key, title in DashboardService.CORE_RESOURCE_TITLES.items()}
        target_titles = list(title_to_key.keys())

        titles_bind = bindparam("titles", expanding=True)
        totals_sql = text(
            """
            SELECT r.title, COUNT(l.id) AS total_lessons
            FROM resources r
            JOIN resource_modules m ON m.resource_id = r.id
            JOIN resource_lessons l ON l.module_id = m.id
            WHERE r.title IN :titles
              AND r.is_published = TRUE
            GROUP BY r.title
            """
        ).bindparams(titles_bind)

        completed_sql = text(
            """
            SELECT r.title, COUNT(p.id) AS completed_lessons
            FROM resources r
            JOIN resource_modules m ON m.resource_id = r.id
            JOIN resource_lessons l ON l.module_id = m.id
            JOIN resource_lesson_progress p ON p.lesson_id = l.id
            WHERE p.user_id = :user_id
              AND r.title IN :titles
              AND r.is_published = TRUE
            GROUP BY r.title
            """
        ).bindparams(titles_bind)

        try:
            total_rows = await session.execute(totals_sql, {"titles": target_titles})
            totals_by_title = {title: count for title, count in total_rows.all()}
        except Exception:
            return {}

        has_course_content = any(totals_by_title.get(title, 0) > 0 for title in target_titles)
        if not has_course_content:
            return {}

        try:
            completed_rows = await session.execute(
                completed_sql,
                {"user_id": user_id, "titles": target_titles},
            )
            completed_by_title = {title: count for title, count in completed_rows.all()}
        except Exception:
            return {}

        return {
            key: DashboardService._percent(
                completed_by_title.get(title, 0),
                totals_by_title.get(title, 0),
            )
            for title, key in title_to_key.items()
        }

    @staticmethod
    async def _get_core_resource_navigation(user_id: UUID, session: AsyncSession) -> Dict[str, str]:
        navigation = {key: "/resources" for key in DashboardService.CORE_RESOURCE_TITLES}
        target_titles = list(DashboardService.CORE_RESOURCE_TITLES.values())

        try:
            resources_result = await session.execute(
                select(ResourceModel)
                .where(
                    ResourceModel.title.in_(target_titles),
                    ResourceModel.is_published.is_(True),
                    ResourceModel.is_locked.is_(False),
                )
                .options(selectinload(ResourceModel.modules).selectinload(ResourceModuleModel.lessons))
            )
            resources = list(resources_result.scalars().all())
        except Exception:
            return navigation
        if not resources:
            return navigation

        resource_by_title: Dict[str, ResourceModel] = {resource.title: resource for resource in resources}
        ordered_lessons_by_title: Dict[str, list] = {}
        all_lesson_ids = []

        for resource in resources:
            ordered_lessons = []
            for module in sorted(resource.modules, key=lambda current: current.position):
                ordered_lessons.extend(sorted(module.lessons, key=lambda current: current.position))
            lesson_ids = [lesson.id for lesson in ordered_lessons]
            ordered_lessons_by_title[resource.title] = lesson_ids
            all_lesson_ids.extend(lesson_ids)

        completed_ids = set()
        if all_lesson_ids:
            try:
                completed_rows = await session.execute(
                    select(ResourceLessonProgressModel.lesson_id).where(
                        ResourceLessonProgressModel.user_id == user_id,
                        ResourceLessonProgressModel.lesson_id.in_(all_lesson_ids),
                    )
                )
                completed_ids = {row[0] for row in completed_rows.all()}
            except Exception:
                return navigation

        for key, title in DashboardService.CORE_RESOURCE_TITLES.items():
            resource = resource_by_title.get(title)
            if not resource:
                continue
            ordered_lesson_ids = ordered_lessons_by_title.get(title, [])
            target_lesson_id = None
            for lesson_id in ordered_lesson_ids:
                if lesson_id not in completed_ids:
                    target_lesson_id = lesson_id
                    break
            if target_lesson_id is None and ordered_lesson_ids:
                target_lesson_id = ordered_lesson_ids[-1]

            if target_lesson_id:
                navigation[key] = f"/resources/{resource.id}?lesson={target_lesson_id}"
            else:
                navigation[key] = f"/resources/{resource.id}"

        return navigation

    @staticmethod
    async def _sync_user_stats_with_resource_progress(
        user_id: UUID,
        session: AsyncSession,
        stats: UserStatsModel,
    ) -> UserStatsModel:
        resource_progress = await DashboardService._get_core_resource_progress(user_id, session)
        if not resource_progress:
            return stats

        resume_progress = resource_progress.get("resume", 0)
        linkedin_progress = resource_progress.get("linkedin", 0)
        interview_progress = resource_progress.get("interview_prep", 0)

        changed = (
            stats.resume_progress != resume_progress
            or stats.linkedin_progress != linkedin_progress
            or stats.interview_progress != interview_progress
        )
        if not changed:
            return stats

        stats.resume_progress = resume_progress
        stats.linkedin_progress = linkedin_progress
        stats.interview_progress = interview_progress
        await session.commit()
        await session.refresh(stats)
        return stats
    
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
