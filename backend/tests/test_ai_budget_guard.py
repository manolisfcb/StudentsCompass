"""Global provider-attempt ceiling.

What is being pinned here is that the ceiling is counted in *provider
attempts* — every request handed to Gemini, retries included — and that it is
refused outright whenever the counter cannot be trusted to be global.
"""
import asyncio

import pytest

import app.config as config
import app.services.ai.aiBudgetGuard as budget_guard
import app.services.ratelimit.counterStore as counter_store
from app.services.ai.aiBudgetGuard import AIBudgetExhausted, ensure_llm_attempt_allowed
from app.services.ratelimit.counterStore import reset_counter_store


async def _attempts_used() -> int:
    store = counter_store.get_counter_store()
    return await store.get_int(budget_guard._global_attempts_key())


class _FakeModels:
    """Provider double. Records every attempt; ``error`` decides the outcome."""

    def __init__(self, error: Exception | None = None):
        self.calls = 0
        self.error = error

    async def generate_content(self, **kwargs):
        self.calls += 1
        if self.error is not None:
            raise self.error
        raise AssertionError("no successful response configured")


class _FakeClient:
    def __init__(self, error: Exception | None = None):
        self.models = _FakeModels(error)
        self.aio = self


@pytest.mark.asyncio
async def test_global_ceiling_trips_after_limit(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 2)

    await ensure_llm_attempt_allowed()
    await ensure_llm_attempt_allowed()

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()


@pytest.mark.asyncio
async def test_attempt_rate_ceiling_trips_within_the_minute(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "AI_LLM_ATTEMPTS_PER_MIN", 2)

    await ensure_llm_attempt_allowed()
    await ensure_llm_attempt_allowed()

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()


@pytest.mark.asyncio
async def test_kill_switch_blocks_immediately(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "AI_KILL_SWITCH", True)

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()

    # Nothing was counted: the switch is checked before any counter is touched.
    assert await _attempts_used() == 0


@pytest.mark.asyncio
async def test_budget_message_maps_to_manual_mode():
    # The exception text contains "quota"/"limit" so the existing friendly-error
    # mapping surfaces the "Manual mode" message without extra wiring.
    from app.services.ai.cvAnalysisService import LLM_QUOTA_MESSAGE, friendly_analysis_error_message

    assert friendly_analysis_error_message(AIBudgetExhausted()) == LLM_QUOTA_MESSAGE


@pytest.mark.asyncio
async def test_production_without_shared_store_refuses_to_authorize_spend(monkeypatch):
    """A per-process ceiling multiplies by replicas and resets on restart, so
    in production it is not a ceiling at all: refuse instead of spending."""
    await reset_counter_store()
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "AI_ALLOW_UNSHARED_COUNTER", False)

    assert counter_store.get_counter_store().is_shared is False

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()


@pytest.mark.asyncio
async def test_failed_redis_init_in_production_does_not_enable_spend(monkeypatch):
    """The store falls back to memory when Redis cannot be constructed. That
    keeps best-effort IP limits alive, but must not authorize LLM spend."""
    monkeypatch.setattr(counter_store, "_store", None)
    monkeypatch.setattr(config, "REDIS_URL", "redis://unreachable.invalid:6379/0")
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "AI_ALLOW_UNSHARED_COUNTER", False)

    def _boom(url):
        raise RuntimeError("redis client could not be created")

    monkeypatch.setattr(counter_store, "RedisCounterStore", _boom)

    store = counter_store.get_counter_store()
    assert isinstance(store, counter_store.InMemoryCounterStore)

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()

    monkeypatch.setattr(counter_store, "_store", None)


@pytest.mark.asyncio
async def test_single_process_deployment_can_opt_in_explicitly(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "IS_PRODUCTION", True)
    monkeypatch.setattr(config, "AI_ALLOW_UNSHARED_COUNTER", True)

    await ensure_llm_attempt_allowed()

    assert await _attempts_used() == 1


@pytest.mark.asyncio
async def test_unreachable_store_fails_closed(monkeypatch):
    class _BrokenStore(counter_store.InMemoryCounterStore):
        is_shared = True

        async def sliding_window_allow(self, key, *, max_requests, window_seconds):
            raise counter_store.CounterStoreError("down")

    monkeypatch.setattr(counter_store, "_store", _BrokenStore())

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()

    monkeypatch.setattr(counter_store, "_store", None)


@pytest.mark.asyncio
async def test_three_provider_attempts_consume_three_global_units(monkeypatch):
    """The bug this task fixes: one guard call used to cover a retry loop that
    sends up to three paid requests."""
    import app.core.resume_analyzer.llm_model as llm_model

    await reset_counter_store()
    fake = _FakeClient(Exception("connection reset by peer"))
    monkeypatch.setattr(llm_model, "client", fake)

    with pytest.raises(RuntimeError):
        await llm_model.ask_llm_model("a sufficiently long resume text", retries=2)

    assert fake.models.calls == 3
    assert await _attempts_used() == 3


@pytest.mark.asyncio
async def test_non_retryable_error_consumes_exactly_one_unit(monkeypatch):
    import app.core.resume_analyzer.llm_model as llm_model

    await reset_counter_store()
    fake = _FakeClient(Exception("429 RESOURCE_EXHAUSTED: quota exceeded"))
    monkeypatch.setattr(llm_model, "client", fake)

    with pytest.raises(RuntimeError):
        await llm_model.ask_llm_model("a sufficiently long resume text", retries=2)

    assert fake.models.calls == 1
    assert await _attempts_used() == 1


@pytest.mark.asyncio
async def test_ceiling_reached_mid_retry_stops_the_remaining_attempts(monkeypatch):
    import app.core.resume_analyzer.llm_model as llm_model

    await reset_counter_store()
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 2)
    fake = _FakeClient(Exception("connection reset by peer"))
    monkeypatch.setattr(llm_model, "client", fake)

    # Raised unwrapped, so the caller can release the user's reserved slot and
    # answer "Manual mode" instead of a generic provider error.
    with pytest.raises(AIBudgetExhausted):
        await llm_model.ask_llm_model("a sufficiently long resume text", retries=5)

    assert fake.models.calls == 2


@pytest.mark.asyncio
async def test_resume_audit_evaluator_counts_and_surfaces_the_ceiling(monkeypatch):
    from app.core.resume_analyzer.resume_audit_llm import GeminiResumeAuditEvaluator

    await reset_counter_store()
    evaluator = GeminiResumeAuditEvaluator(retries=2)
    fake = _FakeClient(Exception("connection reset by peer"))
    evaluator.client = fake

    with pytest.raises(RuntimeError):
        await evaluator.evaluate("a sufficiently long resume text for the audit")

    assert fake.models.calls == 3
    assert await _attempts_used() == 3

    # And once the ceiling is reached, the evaluator surfaces it unwrapped so
    # the course-audit route answers 503 / "Manual mode".
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 3)
    with pytest.raises(AIBudgetExhausted):
        await evaluator.evaluate("a sufficiently long resume text for the audit")


@pytest.mark.asyncio
async def test_two_replicas_share_one_ceiling(monkeypatch):
    """Two guards holding *different* store objects that talk to the same
    backend must not each get a full allowance. The fast lane can only fake the
    backend; tests/integration/test_redis_counter_store.py runs the real thing.
    """
    shared_state: dict[str, int] = {}

    class _ReplicaStore(counter_store.InMemoryCounterStore):
        is_shared = True

        async def incr(self, key, *, ttl_seconds, amount=1):
            shared_state[key] = shared_state.get(key, 0) + amount
            return shared_state[key]

        async def get_int(self, key):
            return shared_state.get(key, 0)

    replica_a, replica_b = _ReplicaStore(), _ReplicaStore()
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 2)

    monkeypatch.setattr(counter_store, "_store", replica_a)
    await ensure_llm_attempt_allowed()
    monkeypatch.setattr(counter_store, "_store", replica_b)
    await ensure_llm_attempt_allowed()

    # The third attempt is refused on whichever replica issues it.
    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()
    monkeypatch.setattr(counter_store, "_store", replica_a)
    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_attempt_allowed()

    monkeypatch.setattr(counter_store, "_store", None)


@pytest.mark.asyncio
async def test_concurrent_attempts_are_not_double_counted(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "AI_GLOBAL_DAILY_ATTEMPTS", 10_000)
    monkeypatch.setattr(config, "AI_LLM_ATTEMPTS_PER_MIN", 10_000)

    await asyncio.gather(*(ensure_llm_attempt_allowed() for _ in range(25)))

    assert await _attempts_used() == 25
