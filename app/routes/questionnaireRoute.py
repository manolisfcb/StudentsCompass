from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.services.accounts.userService import current_active_user
from app.models.userModel import User
from app.schemas.questionnaireSchema import QuestionnaireRead, QuestionnaireSubmit, QuestionnaireResult
from app.services.accounts.questionnaireService import QuestionnaireService

router = APIRouter()

@router.get("/questionnaire", response_model=QuestionnaireRead)
async def get_questionnaire(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user)
):
    service = QuestionnaireService(session)
    return await service.get_questionnaire()

@router.post("/questionnaire", response_model=QuestionnaireResult)
async def submit_questionnaire(
    submit: QuestionnaireSubmit,
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user)
):
    service = QuestionnaireService(session)
    return await service.submit_questionnaire(user.id, submit)

@router.get("/questionnaire/profile")
async def get_user_profile(
    session: AsyncSession = Depends(get_session),
    user: User = Depends(current_active_user)
):
    """
    Obtiene el perfil completo del usuario con sus respuestas y resultados del último cuestionario completado
    """
    try:
        return await QuestionnaireService(session).get_user_questionnaire_profile(user)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
