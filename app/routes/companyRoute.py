from fastapi import APIRouter, Depends, HTTPException
from app.services.companyService import fastapi_companies, current_active_company, auth_backend_company
from app.schemas.companySchema import CompanyCreate, CompanyRead, CompanyUpdate

router = APIRouter()

# Include company authentication routes
router.include_router(
    fastapi_companies.get_auth_router(auth_backend_company),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company registration routes
router.include_router(
    fastapi_companies.get_register_router(CompanyRead, CompanyCreate),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company reset password routes
router.include_router(
    fastapi_companies.get_reset_password_router(),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company verification routes
router.include_router(
    fastapi_companies.get_verify_router(CompanyRead),
    prefix="/auth/company",
    tags=["company-auth"]
)

# Include company users routes (for updating profile, etc.)
router.include_router(
    fastapi_companies.get_users_router(CompanyRead, CompanyUpdate),
    prefix="/companies",
    tags=["companies"]
)
