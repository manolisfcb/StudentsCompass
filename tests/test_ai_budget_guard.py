import pytest

import app.config as config
import app.services.ai.aiBudgetGuard as budget_guard
from app.services.ai.aiBudgetGuard import AIBudgetExhausted, ensure_llm_budget
from app.services.ratelimit.counterStore import reset_counter_store


@pytest.mark.asyncio
async def test_global_budget_trips_after_ceiling(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(budget_guard, "AI_GLOBAL_DAILY_BUDGET", 2)

    await ensure_llm_budget()
    await ensure_llm_budget()

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_budget()


@pytest.mark.asyncio
async def test_kill_switch_blocks_immediately(monkeypatch):
    await reset_counter_store()
    monkeypatch.setattr(config, "AI_KILL_SWITCH", True)

    with pytest.raises(AIBudgetExhausted):
        await ensure_llm_budget()


@pytest.mark.asyncio
async def test_budget_message_maps_to_manual_mode(monkeypatch):
    # The exception text contains "quota"/"limit" so the existing friendly-error
    # mapping surfaces the "Manual mode" message without extra wiring.
    from app.services.ai.cvAnalysisService import LLM_QUOTA_MESSAGE, friendly_analysis_error_message

    assert friendly_analysis_error_message(AIBudgetExhausted()) == LLM_QUOTA_MESSAGE
