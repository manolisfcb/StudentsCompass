from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.services.companyService import current_active_company, current_active_company_recruiter
from app.services.userService import current_active_user
from app.services.applicationService import ApplicationService
from app.services.dashboardService import DashboardService
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.schemas.applicationSchema import (
    ApplicationCreate,
    ApplicationEligibleResumeRead,
    ApplicationRead,
    ApplicationUpdate,
)
from typing import Dict, List
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/company_dashboard", response_model=Dict)
async def get_company_dashboard(
    company: Company = Depends(current_active_company),
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
    session: AsyncSession = Depends(get_session),
):
    """
    Get complete dashboard data for companies.
    """
    logger.info(f"Company dashboard request received for company: {company.id if company else 'None'}")

    if not company:
        logger.error("No company found in request")
        raise HTTPException(status_code=404, detail="Company not found")

    try:
        logger.info(f"Fetching dashboard data for company {company.id}")
        dashboard_data = await DashboardService.get_company_dashboard(company.id, session)
        dashboard_data["current_recruiter"] = {
            "id": str(recruiter.id),
            "email": recruiter.email,
            "first_name": recruiter.first_name,
            "last_name": recruiter.last_name,
            "role": recruiter.role,
            "is_active": recruiter.is_active,
        }
        logger.info(f"Company dashboard data fetched successfully for company {company.id}")
        return dashboard_data
    except Exception as e:
        logger.error(f"Error fetching company dashboard for company {company.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching company dashboard data: {str(e)}")


@router.get("/students_dashboard", response_model=Dict)
async def get_students_dashboard(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get complete dashboard data for students
    """
    logger.info(f"Dashboard request received for user: {user.id if user else 'None'}")
    
    if not user:
        logger.error("No user found in request")
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        logger.info(f"Fetching dashboard data for user {user.id}")
        dashboard_data = await DashboardService.get_student_dashboard(user.id, session)
        logger.info(f"Dashboard data fetched successfully for user {user.id}")
        return dashboard_data
    except Exception as e:
        logger.error(f"Error fetching dashboard data for user {user.id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")


@router.get("/dashboard/stats", response_model=Dict)
async def get_dashboard_stats(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get dashboard statistics for the current user
    """
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    try:
        dashboard_data = await DashboardService.get_user_dashboard_data(user.id, session)
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard data: {str(e)}")


@router.post("/applications", response_model=ApplicationRead)
async def create_application(
    application: ApplicationCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new job application
    """
    application_service = ApplicationService(session)
    new_application = await application_service.create_application(
        user_id=user.id,
        payload=application,
    )
    return new_application


@router.get("/applications/eligible-resumes", response_model=List[ApplicationEligibleResumeRead])
async def get_eligible_resumes_for_application(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    application_service = ApplicationService(session)
    approved_resumes = await application_service.list_approved_resumes(user_id=user.id)
    return [
        ApplicationEligibleResumeRead(
            id=option.resume.id,
            original_filename=option.resume.original_filename,
            created_at=option.resume.created_at,
            ai_summary=option.resume.ai_summary,
            contact_phone=option.resume.contact_phone,
            overall_score=round(option.overall_score, 1),
            approved_at=option.approved_at,
            is_latest=index == 0,
        )
        for index, option in enumerate(approved_resumes)
    ]


@router.get("/applications", response_model=List[ApplicationRead])
async def get_applications(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all applications for the current user
    """
    application_service = ApplicationService(session)
    applications = await application_service.list_user_applications(user_id=user.id)
    return applications


@router.patch("/applications/{application_id}", response_model=ApplicationRead)
async def update_application(
    application_id: UUID,
    application_update: ApplicationUpdate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Update an existing application
    """
    application_service = ApplicationService(session)
    application = await application_service.update_application(
        application_id=application_id,
        user_id=user.id,
        payload=application_update,
    )
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    return application


@router.delete("/applications/{application_id}")
async def delete_application(
    application_id: UUID,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Delete an application
    """
    application_service = ApplicationService(session)
    deleted = await application_service.delete_application(
        application_id=application_id,
        user_id=user.id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Application not found")
    return {"message": "Application deleted successfully"}
