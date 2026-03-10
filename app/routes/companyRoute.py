import html
import mimetypes
from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import HTMLResponse
from fastapi_users.password import PasswordHelper
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ResumeAnalizer.resume_text_extractor import extract_resume_text_from_bytes
from app.db import get_session
from app.models.companyModel import Company
from app.models.companyRecruiterModel import CompanyRecruiter
from app.models.applicationModel import ApplicationModel
from app.schemas.companyApplicantSchema import (
    CompanyApplicantApplicationRead,
    CompanyApplicantCandidateRead,
    CompanyApplicantRead,
    CompanyApplicantResumeRead,
)
from app.schemas.companyRecruiterSchema import (
    CompanyRecruiterCreate,
    CompanyRecruiterManagementRead,
    CompanyRecruiterManagementUpdate,
    CompanyRecruiterRead,
)
from app.schemas.companySchema import CompanyCreate, CompanyRead, CompanyUpdate
from app.services.companyApplicantService import CompanyApplicantService
from app.services.companyRecruiterService import CompanyRecruiterService
from app.services.companyService import (
    auth_backend_company,
    current_active_company,
    current_active_company_recruiter,
    current_company_owner_recruiter,
    fastapi_company_recruiters,
)
from app.services.resumeService import ResumeService

router = APIRouter()


def _build_resume_preview_html(*, filename: str, body: str, title: str = "Resume preview") -> str:
    safe_title = html.escape(title)
    safe_filename = html.escape(filename or "resume")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_title}</title>
    <style>
      :root {{
        color-scheme: light;
      }}
      body {{
        margin: 0;
        font-family: Georgia, "Times New Roman", serif;
        background: #f8fafc;
        color: #0f172a;
      }}
      .page {{
        max-width: 860px;
        margin: 0 auto;
        padding: 2rem;
      }}
      .sheet {{
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 18px;
        box-shadow: 0 20px 45px rgba(15, 23, 42, 0.08);
        padding: 2rem;
      }}
      .eyebrow {{
        margin: 0 0 0.35rem;
        font: 700 0.72rem/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #0f766e;
      }}
      h1 {{
        margin: 0 0 1.5rem;
        font: 700 1.45rem/1.2 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .content p {{
        margin: 0 0 1rem;
        font-size: 1rem;
        line-height: 1.72;
        white-space: pre-wrap;
      }}
      .empty {{
        margin: 0;
        padding: 1rem 1.1rem;
        border-radius: 12px;
        background: #fef3c7;
        color: #92400e;
        font: 500 0.96rem/1.6 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
    </style>
  </head>
  <body>
    <main class="page">
      <section class="sheet">
        <p class="eyebrow">Generated preview</p>
        <h1>{safe_filename}</h1>
        {body}
      </section>
    </main>
  </body>
</html>"""


def _build_docx_preview_body(extracted_text: str) -> str:
    paragraphs = [line.strip() for line in (extracted_text or "").splitlines() if line.strip()]
    if not paragraphs:
        return (
            '<p class="empty">We could not render a rich preview for this Word document. '
            'Use the download action to inspect the original file.</p>'
        )
    return '<div class="content">' + "".join(
        f"<p>{html.escape(paragraph)}</p>" for paragraph in paragraphs
    ) + "</div>"


def _is_docx_previewable(*, filename: str, media_type: str) -> bool:
    normalized = (filename or "").lower()
    return normalized.endswith(".docx") or media_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _is_legacy_doc(*, filename: str, media_type: str) -> bool:
    normalized = (filename or "").lower()
    return normalized.endswith(".doc") or media_type == "application/msword"


def _build_company_applicant_payload(application: ApplicationModel) -> CompanyApplicantRead:
    user = application.user
    resume = application.resume
    full_name = " ".join(part for part in [user.first_name if user else None, user.last_name if user else None] if part).strip()
    if not full_name:
        full_name = user.nickname if user and user.nickname else (user.email if user else "Candidate")

    resume_payload = None
    if resume is not None:
        preview_url = f"/api/v1/companies/me/applications/{application.id}/resume/preview"
        download_url = f"/api/v1/companies/me/applications/{application.id}/resume/download"
        resume_payload = CompanyApplicantResumeRead(
            id=resume.id,
            original_filename=resume.original_filename,
            uploaded_at=resume.created_at,
            summary=resume.ai_summary,
            phone=resume.contact_phone,
            preview_url=preview_url,
            download_url=download_url,
        )

    return CompanyApplicantRead(
        application=CompanyApplicantApplicationRead(
            id=application.id,
            job_posting_id=application.job_posting_id,
            job_title=application.job_title,
            status=application.status.value if hasattr(application.status, "value") else str(application.status),
            application_date=application.application_date,
            assigned_recruiter_id=application.assigned_recruiter_id,
            notes=application.notes,
        ),
        candidate=CompanyApplicantCandidateRead(
            id=user.id,
            first_name=user.first_name,
            last_name=user.last_name,
            full_name=full_name,
            email=user.email,
            phone=user.phone or (resume.contact_phone if resume else None),
            address=user.address,
            sex=user.sex,
            age=user.age,
        ),
        resume=resume_payload,
        certifications=[],
    )


# Include company authentication routes
router.include_router(
    fastapi_company_recruiters.get_auth_router(auth_backend_company),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Company registration (creates company + initial recruiter)
@router.post("/auth/company/register", response_model=CompanyRead, status_code=status.HTTP_201_CREATED)
async def register_company_with_initial_recruiter(
    payload: CompanyCreate,
    session: AsyncSession = Depends(get_session),
):
    existing_recruiter = await session.execute(
        select(CompanyRecruiter).where(CompanyRecruiter.email == payload.email)
    )
    if existing_recruiter.scalar_one_or_none() is not None:
        raise HTTPException(status_code=400, detail="REGISTER_USER_ALREADY_EXISTS")

    password_helper = PasswordHelper()
    hashed_password = password_helper.hash(payload.password)

    company = Company(
        company_name=payload.company_name,
        industry=payload.industry,
        description=payload.description,
        website=payload.website,
        location=payload.location,
        contact_person=payload.contact_person,
        phone=payload.phone,
    )
    session.add(company)
    await session.flush()

    recruiter = CompanyRecruiter(
        company_id=company.id,
        email=payload.email,
        hashed_password=hashed_password,
        is_active=True,
        is_superuser=False,
        is_verified=True,
        first_name=payload.recruiter_first_name or payload.contact_person,
        last_name=payload.recruiter_last_name,
        role="owner",
    )
    session.add(recruiter)

    await session.commit()
    await session.refresh(company)
    return company


# Include company recruiter reset password routes
router.include_router(
    fastapi_company_recruiters.get_reset_password_router(),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company recruiter verification routes
router.include_router(
    fastapi_company_recruiters.get_verify_router(CompanyRecruiterRead),
    prefix="/auth/company",
    tags=["company-auth"]
)

@router.get("/companies/me", response_model=CompanyRead)
async def get_current_company_profile(
    company: Company = Depends(current_active_company),
):
    return company


@router.patch("/companies/me", response_model=CompanyRead)
async def update_current_company_profile(
    payload: CompanyUpdate,
    company: Company = Depends(current_active_company),
    session: AsyncSession = Depends(get_session),
):
    updatable_fields = (
        "company_name",
        "industry",
        "description",
        "website",
        "location",
        "contact_person",
        "phone",
    )
    update_data = payload.model_dump(exclude_unset=True)

    for field in updatable_fields:
        if field in update_data:
            setattr(company, field, update_data[field])

    await session.commit()
    await session.refresh(company)
    return company


@router.get("/companies/me/recruiters", response_model=List[CompanyRecruiterManagementRead])
async def list_company_recruiters(
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.list_company_recruiters(owner_recruiter.company_id)


@router.post(
    "/companies/me/recruiters",
    response_model=CompanyRecruiterManagementRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_company_recruiter(
    payload: CompanyRecruiterCreate,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.create_company_recruiter(owner_recruiter.company_id, payload)


@router.patch("/companies/me/recruiters/{recruiter_id}", response_model=CompanyRecruiterManagementRead)
async def update_company_recruiter(
    recruiter_id: UUID,
    payload: CompanyRecruiterManagementUpdate,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    return await recruiter_service.update_company_recruiter(
        company_id=owner_recruiter.company_id,
        recruiter_id=recruiter_id,
        actor_recruiter_id=owner_recruiter.id,
        payload=payload,
    )


@router.delete("/companies/me/recruiters/{recruiter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_company_recruiter(
    recruiter_id: UUID,
    owner_recruiter: CompanyRecruiter = Depends(current_company_owner_recruiter),
    session: AsyncSession = Depends(get_session),
):
    recruiter_service = CompanyRecruiterService(session)
    await recruiter_service.delete_company_recruiter(
        company_id=owner_recruiter.company_id,
        recruiter_id=recruiter_id,
        actor_recruiter_id=owner_recruiter.id,
    )


@router.get("/companies/me/recruiters/current", response_model=CompanyRecruiterManagementRead)
async def get_current_company_recruiter_profile(
    recruiter: CompanyRecruiter = Depends(current_active_company_recruiter),
):
    return recruiter


@router.get("/companies/me/applicants", response_model=List[CompanyApplicantRead])
async def list_company_applicants(
    company: Company = Depends(current_active_company),
    job_posting_id: UUID | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
):
    applicant_service = CompanyApplicantService(session)
    applications = await applicant_service.list_company_applicants(
        company_id=company.id,
        job_posting_id=job_posting_id,
    )
    return [_build_company_applicant_payload(application) for application in applications]


async def _get_company_resume_response(
    *,
    company: Company,
    application_id: UUID,
    session: AsyncSession,
    disposition: str,
) -> Response:
    applicant_service = CompanyApplicantService(session)
    application = await applicant_service.get_company_application(
        company_id=company.id,
        application_id=application_id,
    )
    if application is None or application.resume is None:
        raise HTTPException(status_code=404, detail="Resume not found for this application")

    resume_service = ResumeService(session)
    file_bytes = await resume_service.download_file_from_s3(application.resume.storage_file_id)
    media_type = mimetypes.guess_type(application.resume.original_filename)[0] or "application/octet-stream"
    filename = application.resume.original_filename or "resume"

    if disposition == "inline":
        if _is_docx_previewable(filename=filename, media_type=media_type):
            extracted_text = await extract_resume_text_from_bytes(
                file_bytes,
                filename=filename,
                content_type=media_type,
            )
            return HTMLResponse(
                content=_build_resume_preview_html(
                    filename=filename,
                    body=_build_docx_preview_body(extracted_text),
                )
            )
        if _is_legacy_doc(filename=filename, media_type=media_type):
            return HTMLResponse(
                content=_build_resume_preview_html(
                    filename=filename,
                    title="Resume preview unavailable",
                    body=(
                        '<p class="empty">Legacy .doc files cannot be rendered safely inside the platform preview. '
                        'Use the download action to inspect the original file.</p>'
                    ),
                )
            )

    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={
            "Content-Disposition": f'{disposition}; filename="{filename}"',
        },
    )


@router.get("/companies/me/applications/{application_id}/resume/preview")
async def preview_company_applicant_resume(
    application_id: UUID,
    company: Company = Depends(current_active_company),
    session: AsyncSession = Depends(get_session),
):
    return await _get_company_resume_response(
        company=company,
        application_id=application_id,
        session=session,
        disposition="inline",
    )


@router.get("/companies/me/applications/{application_id}/resume/download")
async def download_company_applicant_resume(
    application_id: UUID,
    company: Company = Depends(current_active_company),
    session: AsyncSession = Depends(get_session),
):
    return await _get_company_resume_response(
        company=company,
        application_id=application_id,
        session=session,
        disposition="attachment",
    )
