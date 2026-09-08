from pydantic import BaseModel


class ResumeFeatureRequest(BaseModel):
    resume_text: str
    resume_summary: str = None
    resume_keywords: list[str] = []
    resume_key_skills: list[str] = []
    