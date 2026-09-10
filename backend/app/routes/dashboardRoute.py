from fastapi import APIRouter, HTTPException, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.idempotency import actor_key, begin_idempotent_request
from app.db import get_session
from app.services.companies.companyService import current_active_company, current_active_company_recruiter
from app.services.accounts.userService import current_active_user
from app.services.applications.applicationService import (
    ApplicationService,
    InvalidApplicationCursor,
)
from app.services.applications.dashboardService import DashboardService
from app.models.userModel import User
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.schemas.applicationSchema import (
    ApplicationCreate,
    ApplicationEligibleResumeRead,
    ApplicationPageRead,
    ApplicationRead,
    ApplicationUpdate,
)
from app.schemas.interviewSchema import InterviewAvailabilitySelectionRequest
from typing import Dict, List
from uuid import UUID
import logging
from app.services.jobs.interviewService import InterviewService
from app.core.errors import (
    CODE_COMPANY_DASHBOARD,
    CODE_DASHBOARD_STATS,
    CODE_STUDENT_DASHBOARD,
    server_failure,
)
from app.schemas.dashboardSchema import StudentDashboardRead

logger = logging.getLogger(__name__)

router = APIRouter()
# TASK-048 (plan 08 §5.2): `/dashboard/student` is the renamed contract React
# consumes; `legacy_router` keeps `/students_dashboard` alive for the Jinja
# dashboard, mounted with `include_in_schema=False` — the same pattern
# TASK-047 used for `/resumes` and TASK-042 used for `/auth/jwt`.
legacy_router = APIRouter()


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
    except Exception as exc:
        # The exception text used to go straight into the public body, and the
        # log line interpolated it unredacted. A driver or storage error carries
        # the DSN, the SQL and its bound parameters.
        raise await server_failure(
            exc,
            logger=logger,
            code=CODE_COMPANY_DASHBOARD,
            message="We could not load the company dashboard right now.",
            session=session,
            context=f"company_id={company.id}",
        )


@router.get("/dashboard/student", response_model=StudentDashboardRead)
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
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=logger,
            code=CODE_STUDENT_DASHBOARD,
            message="We could not load your dashboard right now.",
            session=session,
            context=f"user_id={user.id}",
        )


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
    except Exception as exc:
        raise await server_failure(
            exc,
            logger=logger,
            code=CODE_DASHBOARD_STATS,
            message="We could not load your dashboard statistics right now.",
            session=session,
            context=f"user_id={user.id}",
        )


@router.post("/applications", response_model=ApplicationRead)
async def create_application(
    request: Request,
    application: ApplicationCreate,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Create a new job application

    Retry-safe when the caller sends ``Idempotency-Key``: applying twice to the
    same posting because a response was lost is a duplicate the student then has
    to explain, so the second call replays the first application instead of
    filing another one.
    """
    guard = await begin_idempotent_request(
        session,
        request=request,
        actor=actor_key("user", user.id),
        endpoint="POST /applications",
        payload=application,
    )
    if guard.is_replay:
        return guard.replay

    application_service = ApplicationService(session)
    try:
        new_application = await application_service.create_application(
            user_id=user.id,
            payload=application,
        )
    except Exception:
        await guard.release()
        raise
    return await guard.store(ApplicationRead.model_validate(new_application))


@router.get("/applications/eligible-resumes", response_model=List[ApplicationEligibleResumeRead])
async def get_eligible_resumes_for_application(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    application_service = ApplicationService(session)
    approved_resumes = await application_service.list_approved_resumes(user_id=user.id)
    return [
        ApplicationEligibleResumeRead.from_option(option, is_latest=index == 0)
        for index, option in enumerate(approved_resumes)
    ]


@router.get("/applications", response_model=List[ApplicationRead])
async def get_applications(
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Get applications for the current user

    Legacy shape: a bare list, newest first, now capped at one window. Callers
    move to the paged endpoint below; the React applications screen is TASK-049.
    """
    application_service = ApplicationService(session)
    applications = await application_service.list_user_applications(user_id=user.id)
    return applications


@router.get("/applications/page", response_model=ApplicationPageRead)
async def get_application_page(
    before: str | None = Query(
        default=None,
        description="Cursor from a previous page's next_cursor; returns older applications.",
    ),
    limit: int = Query(
        default=ApplicationService.DEFAULT_APPLICATION_PAGE_SIZE,
        ge=1,
        le=ApplicationService.MAX_APPLICATION_PAGE_SIZE,
    ),
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    """One bounded page of the caller's own applications, newest first."""
    application_service = ApplicationService(session)
    try:
        rows, next_cursor, has_more, page_size = (
            await application_service.list_user_application_page(
                user_id=user.id, before=before, limit=limit
            )
        )
    except InvalidApplicationCursor as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ApplicationPageRead(
        items=[ApplicationRead.model_validate(row) for row in rows],
        next_cursor=next_cursor,
        has_more=has_more,
        limit=page_size,
    )


@router.post("/applications/{application_id}/interview-selection", response_model=ApplicationRead)
async def select_interview_availability(
    application_id: UUID,
    payload: InterviewAvailabilitySelectionRequest,
    user: User = Depends(current_active_user),
    session: AsyncSession = Depends(get_session),
):
    interview_service = InterviewService(session)
    return await interview_service.select_user_availability(
        application_id=application_id,
        slot_id=payload.slot_id,
        user=user,
    )


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


# --- Legacy adapter (TASK-048, plan 08 §13) -----------------------------------
#
# Same function, old path, hidden from the OpenAPI document. `dashboard.js`
# keeps calling `/students_dashboard` until TASK-059 confirms zero traffic.
legacy_router.add_api_route(
    "/students_dashboard",
    get_students_dashboard,
    methods=["GET"],
    response_model=Dict,
    include_in_schema=False,
)
