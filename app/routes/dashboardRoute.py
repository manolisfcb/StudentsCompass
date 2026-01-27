from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.services.userService import current_active_user
from app.services.dashboardService import DashboardService
from app.models.userModel import User
from app.models.applicationModel import ApplicationModel
from app.schemas.applicationSchema import ApplicationCreate, ApplicationRead, ApplicationUpdate
from typing import Dict, List
from uuid import UUID
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


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
    new_application = ApplicationModel(
        user_id=user.id,
        company_id=application.company_id,
        job_posting_id=application.job_posting_id,
        job_title=application.job_title,
        status=application.status,
        application_url=application.application_url,
        notes=application.notes
    )
    
    session.add(new_application)
    await session.commit()
    await session.refresh(new_application)
    
    return new_application


@router.get("/applications", response_model=List[ApplicationRead])
async def get_applications(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get all applications for the current user
    """
    from sqlalchemy import select
    
    query = select(ApplicationModel).where(ApplicationModel.user_id == user.id)
    result = await session.execute(query)
    applications = result.scalars().all()
    
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
    from sqlalchemy import select
    
    query = select(ApplicationModel).where(
        ApplicationModel.id == application_id,
        ApplicationModel.user_id == user.id
    )
    result = await session.execute(query)
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    # Update fields
    update_data = application_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(application, field, value)
    
    await session.commit()
    await session.refresh(application)
    
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
    from sqlalchemy import select, delete
    
    query = select(ApplicationModel).where(
        ApplicationModel.id == application_id,
        ApplicationModel.user_id == user.id
    )
    result = await session.execute(query)
    application = result.scalar_one_or_none()
    
    if not application:
        raise HTTPException(status_code=404, detail="Application not found")
    
    await session.delete(application)
    await session.commit()
    
    return {"message": "Application deleted successfully"}
