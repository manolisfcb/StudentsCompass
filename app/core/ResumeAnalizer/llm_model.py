from google import genai

from app.core.ResumeAnalizer.resume_feature import ResumeFeatureRequest
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

client = genai.Client(api_key=os.getenv("GENAI_API_KEY"))

# Limitar concurrencia: máximo 10 llamadas simultáneas a Gemini
LLM_SEMAPHORE = asyncio.Semaphore(10)

# Timeout para llamadas al LLM (30 segundos)
LLM_TIMEOUT = 30.0

prompt_template = """You are an expert resume analyzer. 
Given the resume text below, extract key information such as skills,
keywords, and provide a concise summary of the resume."""

async def ask_llm_model(prompt: str, model: str = "gemini-3-flash-preview") -> ResumeFeatureRequest:
    """
    Async function using native Google GenAI async client with concurrency control.
    
    Args:
        prompt: Full prompt including resume text
        model: Gemini model to use
        
    Returns:
        ResumeFeatureRequest object with extracted features
        
    Raises:
        asyncio.TimeoutError: If LLM call exceeds timeout
        Exception: Any error from the API
    """
    async with LLM_SEMAPHORE:
        try:
            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "response_mime_type": "application/json",
                        "response_json_schema": ResumeFeatureRequest.model_json_schema(),
                    },
                ),
                timeout=LLM_TIMEOUT
            )
            resume_features = ResumeFeatureRequest.model_validate_json(response.text)
            return resume_features
        except asyncio.TimeoutError:
            raise asyncio.TimeoutError(f"LLM call exceeded {LLM_TIMEOUT}s timeout")
        except Exception as e:
            raise Exception(f"LLM API error: {str(e)}")