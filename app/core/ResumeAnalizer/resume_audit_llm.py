from __future__ import annotations

import asyncio
import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from google import genai

from app.core.ResumeAnalizer.prompts.resume_audit_prompt import (
    build_resume_audit_system_prompt,
    build_resume_audit_user_prompt,
)
from app.core.ResumeAnalizer.resume_audit_schema import ResumeAuditResult

load_dotenv()

API_KEY = os.getenv("GENAI_API_KEY")
MAX_RESUME_CHARS = 80_000
LLM_TIMEOUT = 45.0
LLM_SEMAPHORE = asyncio.Semaphore(8)
INJECTION_PATTERNS = (
    r"ignore\s+previous\s+instructions",
    r"disregard\s+all\s+instructions",
    r"system\s*prompt",
    r"you\s+are\s+chatgpt",
    r"developer\s+message",
    r"assistant\s*:",
    r"<\s*system\s*>",
    r"jailbreak",
)


@dataclass
class PromptSanitizationResult:
    safe_resume_text: str
    detected_signals: list[str]


class ResumePromptInjectionGuard:
    """Sanitizes untrusted resume text and flags prompt-injection signals."""

    @staticmethod
    def sanitize(raw_resume_text: str, max_chars: int = MAX_RESUME_CHARS) -> PromptSanitizationResult:
        text = (raw_resume_text or "").replace("\x00", " ")
        text = re.sub(r"[\x01-\x08\x0B\x0C\x0E-\x1F\x7F]", " ", text)
        text = text.strip()
        if len(text) > max_chars:
            text = text[:max_chars]

        detected: list[str] = []
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text, flags=re.IGNORECASE):
                detected.append(pattern)

        # Keep data verbatim-like while neutralizing role-like headers.
        neutralized = re.sub(r"(?im)^\s*(system|assistant|developer)\s*:\s*", "role_text: ", text)
        return PromptSanitizationResult(safe_resume_text=neutralized, detected_signals=detected)


class ResumeAuditEvaluator(ABC):
    """Strategy interface for pluggable resume-audit evaluators."""

    @abstractmethod
    async def evaluate(self, resume_text: str) -> ResumeAuditResult:
        raise NotImplementedError


class GeminiResumeAuditEvaluator(ResumeAuditEvaluator):
    def __init__(
        self,
        *,
        model: str = "gemini-2.5-flash",
        timeout: float = LLM_TIMEOUT,
        retries: int = 2,
    ) -> None:
        self.model = model
        self.timeout = timeout
        self.retries = retries
        self.client: Optional[genai.Client] = genai.Client(api_key=API_KEY) if API_KEY else None

    async def evaluate(self, resume_text: str) -> ResumeAuditResult:
        if self.client is None:
            raise RuntimeError("LLM service is not configured (missing GENAI_API_KEY).")

        sanitization = ResumePromptInjectionGuard.sanitize(resume_text)
        user_prompt = build_resume_audit_user_prompt(
            sanitization.safe_resume_text,
            detected_signals=sanitization.detected_signals,
        )
        output_schema = ResumeAuditResult.model_json_schema()

        async with LLM_SEMAPHORE:
            last_error: Optional[Exception] = None
            for attempt in range(self.retries + 1):
                try:
                    system_prompt = build_resume_audit_system_prompt()
                    response = await asyncio.wait_for(
                        self.client.aio.models.generate_content(
                            model=self.model,
                            contents=user_prompt,
                            config={
                                "system_instruction": system_prompt,
                                "response_mime_type": "application/json",
                                "response_json_schema": output_schema,
                                "temperature": 0.2,
                            },
                        ),
                        timeout=self.timeout,
                    )
                    text = (response.text or "").strip()
                    if not text:
                        raise RuntimeError("Empty response from LLM.")

                    parsed = ResumeAuditResult.model_validate_json(text)
                    parsed.pass_status = parsed.overall_score >= 8
                    parsed.prompt_injection_signals_detected = sanitization.detected_signals
                    return parsed
                except Exception as exc:  # noqa: BLE001
                    last_error = exc
                    if attempt >= self.retries:
                        break
                    await asyncio.sleep(0.6 * (attempt + 1))

        raise RuntimeError(f"Resume audit LLM call failed: {last_error}") from last_error


def serialize_resume_audit_result(result: ResumeAuditResult) -> str:
    """Stable JSON serialization for DB persistence."""
    return json.dumps(result.model_dump(), ensure_ascii=False)
