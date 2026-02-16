from __future__ import annotations

import asyncio
import os
from typing import Optional

from dotenv import load_dotenv
from google import genai

from app.core.ResumeAnalizer.resume_feature import ResumeFeatureRequest

load_dotenv()

API_KEY = os.getenv("GENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("Missing GENAI_API_KEY in environment (.env).")

client = genai.Client(api_key=API_KEY)

# Limitar concurrencia: máximo 10 llamadas simultáneas a Gemini
LLM_SEMAPHORE = asyncio.Semaphore(10)

# Timeout para llamadas al LLM (segundos)
LLM_TIMEOUT = 30.0

MAX_RESUME_CHARS = 60_000

PROMPT_TEMPLATE = """
You are an ATS-grade resume parser and job-search keyword strategist.
Extract structured keywords and signals from the resume text to power online job searches.

# OUTPUT REQUIREMENTS (CRITICAL)
- Output MUST be valid JSON.
- Output MUST strictly conform to the provided JSON Schema (in your tool config).
- Do NOT include markdown, comments, explanations, or extra keys.
- If a field is unknown, use null or an empty list (depending on schema type).
- NEVER invent employers, dates, degrees, certifications, tools, or titles not present in the resume.
- Prefer exact phrasing from the resume for keywords.

# CONTEXT
The resume text may contain:
- formatting artifacts (headers, footers, duplicated lines, weird spacing)
- multiple languages
- inconsistent section titles
Your job is to infer structure but only extract what is supported by the text.

# REFERENCES (WHAT TO EXTRACT)
Focus on producing keywords useful for job searching:
1) Role targets: likely job titles the candidate fits (primary + secondary)
2) Core skills: hard skills, tools, frameworks, platforms, cloud, databases
3) Domain keywords: industries and business domains (e.g., fintech, healthcare, e-commerce)
4) Methods/process: Agile, Scrum, CI/CD, MLOps, data modeling, etc.
5) Seniority signals: years of experience (if stated), leadership/ownership terms
6) Location/authorization: location(s), work authorization, relocation/remote preferences (if present)
7) Certifications and education keywords
8) Must-have search strings:
   - A) Boolean query for LinkedIn jobs
   - B) Boolean query for Indeed
   - C) A short list of 10–20 “exact-match” keywords (quoted terms) for ATS filters

# NORMALIZATION RULES
- Deduplicate keywords.
- Keep keyword casing as commonly used (e.g., "AWS", "SQL", "FastAPI").
- Expand abbreviations ONLY if the resume explicitly implies them (e.g., "NLP" -> "Natural Language Processing" only if both appear).
- Do not output soft skills unless they appear repeatedly and are job-relevant.

# RESUME TEXT (SOURCE OF TRUTH)
{resume_text}
"""


def build_resume_prompt(resume_text: str) -> str:
    """Builds the prompt and applies a safety trim for very large resumes."""
    if not resume_text:
        resume_text = ""
    safe_text = resume_text.strip()
    if len(safe_text) > MAX_RESUME_CHARS:
        safe_text = safe_text[:MAX_RESUME_CHARS]
    return PROMPT_TEMPLATE.format(resume_text=safe_text)


async def ask_llm_model(
    resume_text: str,
    model: str = "gemini-3-flash-preview",
    timeout: float = LLM_TIMEOUT,
    retries: int = 2,
) -> ResumeFeatureRequest:
    """
    Async function using Google GenAI async client with concurrency control.

    Args:
        resume_text: Raw resume text (already extracted from PDF/DOCX)
        model: Gemini model to use
        timeout: Timeout for the LLM call
        retries: Number of retries on transient failures

    Returns:
        ResumeFeatureRequest object with extracted features

    Raises:
        asyncio.TimeoutError: If LLM call exceeds timeout
        RuntimeError: If response cannot be validated as ResumeFeatureRequest
        Exception: Any other API/client error
    """
    prompt = build_resume_prompt(resume_text)
    schema = ResumeFeatureRequest.model_json_schema()

    last_err: Optional[Exception] = None

    async with LLM_SEMAPHORE:
        for attempt in range(retries + 1):
            try:
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=prompt,
                        config={
                            "response_mime_type": "application/json",
                            "response_json_schema": schema,
                        },
                    ),
                    timeout=timeout,
                )

                # Muchas veces esto ya es JSON puro. Pero por seguridad:
                text = (response.text or "").strip()
                if not text:
                    raise RuntimeError("Empty response from LLM.")

                # Validación estricta según tu Pydantic model
                return ResumeFeatureRequest.model_validate_json(text)

            except asyncio.TimeoutError as e:
                last_err = e
                if attempt >= retries:
                    raise asyncio.TimeoutError(f"LLM call exceeded {timeout}s timeout") from e
                await asyncio.sleep(0.5 * (attempt + 1))

            except Exception as e:
                last_err = e
                # reintentar en errores transitorios (red/429/500) sin overthink:
                if attempt >= retries:
                    raise RuntimeError(f"LLM API/validation error: {e}") from e
                await asyncio.sleep(0.5 * (attempt + 1))

    # Teóricamente no llega aquí
    raise RuntimeError(f"LLM failed unexpectedly: {last_err}") from last_err
