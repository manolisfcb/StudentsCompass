from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db import get_session
from app.services.userService import current_active_user
from app.models.userModel import User
from app.schemas.questionnaireSchema import QuestionnaireRead, QuestionnaireSubmit, QuestionnaireResult
from app.services.questionnaireService import QuestionnaireService
from sqlalchemy import select, desc

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
    try:
        print("Fetching profile for user:", user.id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    """
    Obtiene el perfil completo del usuario con sus respuestas y resultados del último cuestionario completado
    """
    try:
        # Get the latest questionnaire response for the user
        from app.models.questionnaireModel import UserQuestionnaire
        from sqlalchemy import desc
        print("Fetching profile for user:", user.id)
        
        stmt = select(UserQuestionnaire).filter(
            UserQuestionnaire.user_id == user.id
        ).order_by(desc(UserQuestionnaire.created_at)).limit(1)
        
        result = await session.execute(stmt)
        user_questionnaire = result.scalar_one_or_none()
        
        if not user_questionnaire:
            raise HTTPException(status_code=404, detail="No questionnaire responses found")
        
        # Get the questionnaire template
        service = QuestionnaireService(session)
        questionnaire = await service.get_questionnaire()
        
        return {
            "user_id": str(user.id),
            "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email.split('@')[0],
            "user_email": user.email,
            "created_at": user_questionnaire.created_at.isoformat(),
            "version": user_questionnaire.version,
            "answers": user_questionnaire.answers,
            "results": user_questionnaire.results,
            "questionnaire": questionnaire
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))