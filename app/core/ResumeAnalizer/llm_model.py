from google import genai

from app.core.ResumeAnalizer.resume_feature import ResumeFeatureRequest
from dotenv import load_dotenv
import os
load_dotenv()

client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))

prompt_template = """You are an expert resume analyzer. 
Given the resume text below, extract key information such as skills,
keywords, and provide a concise summary of the resume."""

def ask_llm_model(prompt: str, model: str = "gemini-3-flash-preview") -> str:
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "response_mime_type": "application/json",
            "response_json_schema": ResumeFeatureRequest.model_json_schema(),
        },
    )
    resume_features = ResumeFeatureRequest.model_validate_json(response.text)
    return resume_features