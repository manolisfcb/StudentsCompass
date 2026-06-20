import pytest

import app.core.resume_analyzer.llm_model as llm_model
from app.core.resume_analyzer.llm_errors import is_non_retryable_llm_error


def test_classifier_flags_quota_and_auth_errors():
    assert is_non_retryable_llm_error(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
    assert is_non_retryable_llm_error(Exception("Invalid API key"))
    assert not is_non_retryable_llm_error(Exception("connection reset by peer"))
    assert not is_non_retryable_llm_error(None)


class _FakeModels:
    def __init__(self):
        self.calls = 0

    async def generate_content(self, **kwargs):
        self.calls += 1
        raise Exception("429 RESOURCE_EXHAUSTED: quota exceeded")


class _FakeAio:
    def __init__(self, models):
        self.models = models


class _FakeClient:
    def __init__(self):
        self.aio = _FakeAio(_FakeModels())


@pytest.mark.asyncio
async def test_ask_llm_model_does_not_retry_quota_errors(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(llm_model, "client", fake)

    with pytest.raises(RuntimeError):
        await llm_model.ask_llm_model("a sufficiently long resume text", retries=2)

    # Quota error must fail fast — no extra (paid) retries.
    assert fake.aio.models.calls == 1
