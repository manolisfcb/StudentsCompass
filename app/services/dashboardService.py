from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.applicationModel import ApplicationModel, ApplicationStatus
from app.models.userModel import User
from app.models.userStatsModel import UserStatsModel
from app.models.resumeModel import ResumeModel
from typing import Dict, List
from uuid import UUID
import logging

logger = logging.getLogger(__name__)


class DashboardService:
    
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
