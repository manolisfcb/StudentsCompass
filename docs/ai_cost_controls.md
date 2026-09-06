# AI cost & abuse controls

This app makes paid LLM calls (Gemini) from two features: CV job-search keyword
extraction and the resume course-audit. The controls below cap what those can
cost, per user and globally, even under hundreds of concurrent users or abuse.

## Layers of protection

1. **Per-user daily quota (atomic).** `AIUsageService.reserve()` claims a slot in
   a shared atomic counter *before* any LLM spend, so concurrent requests cannot
   race past the limit. The durable ledger (`AIUsageEventModel`) is the source of
   truth; the counter is seeded from it so a counter reset never hands back
   already-spent quota.
2. **Global attempt ceiling + kill switch.**
   `aiBudgetGuard.ensure_llm_attempt_allowed()` enforces a hard ceiling on total
   *provider attempts*/day across all users plus a per-minute attempt-rate cap.
   It is applied inside each evaluator, immediately before every individual
   request to Gemini, so a retry consumes its own unit — the guard used to run
   once per user request while the evaluator below it sent up to three. It
   **fails closed** (falls back to "Manual mode") when the counter store is
   unreachable, and also when the store is not shared while `ENV=production`,
   because a per-process ceiling multiplies by replicas and resets on restart.
   `AI_KILL_SWITCH=1` disables all LLM calls instantly.
3. **Registration limits.** Scripted account farming (each account unlocks free
   quota) is throttled by a per-IP burst limit and a per-IP daily account cap.
4. **Verification gate (ready, off by default).** `current_ai_user` requires a
   verified email when `REQUIRE_VERIFIED_FOR_AI=1`. Leave it off until a real
   email provider is configured, then flip it on (backfill `is_verified=true`
   for existing users first so nobody is locked out).
5. **Upload size cap, no-retry on quota errors, docs hidden in prod.**

Counters are shared across replicas when `REDIS_URL` is set (Redis). Without it,
an in-memory per-process fallback is used (fine for local/dev; not shared). In
production that fallback does not authorize LLM spend: the guard refuses and the
features fall back to "Manual mode" until `REDIS_URL` works, unless
`AI_ALLOW_UNSHARED_COUNTER=1` explicitly accepts a single-process ceiling. IP
rate limits keep working on the fallback — they are best-effort and fail open.

## Three units, kept apart

`AI_BASE_DAILY_LIMIT` counts **user units** (what a person may spend per day).
`AI_GLOBAL_DAILY_ATTEMPTS` and `AI_LLM_ATTEMPTS_PER_MIN` count **provider
attempts** (individual requests to Gemini, retries included). Neither is an
amount of **money**: nothing in the app measures spend in currency, so no
request count is described as a budget in money terms. One user unit can cost
several attempts, which is exactly why the global ceilings are counted at the
attempt level.

## Configuration (env vars)

| Var | Default | Meaning |
|---|---|---|
| `REDIS_URL` | _(unset → in-memory)_ | Shared counter/limit backend |
| `AI_BASE_DAILY_LIMIT` | `3` | Free daily AI requests per user/feature |
| `AI_GLOBAL_DAILY_ATTEMPTS` | `2000` | Hard ceiling: provider attempts/day, all users (was `AI_GLOBAL_DAILY_BUDGET`, still read) |
| `AI_LLM_ATTEMPTS_PER_MIN` | `60` | Cross-replica attempt-rate cap (was `AI_LLM_CALLS_PER_MIN`, still read) |
| `AI_ALLOW_UNSHARED_COUNTER` | `0` | `1` accepts a per-process ceiling in production (single process only) |
| `AI_KILL_SWITCH` | `0` | `1` disables all LLM calls immediately |
| `REQUIRE_VERIFIED_FOR_AI` | `0` | `1` requires verified email for AI |
| `MAX_UPLOAD_BYTES` | `5000000` | Max resume upload size (413 above) |
| `REGISTER_RATE_LIMIT_MAX` / `_WINDOW_SECONDS` | `5` / `3600` | Register burst limit per IP |
| `REGISTER_IP_DAILY_ACCOUNT_CAP` | `5` | Accounts/IP/day |
| `FORWARDED_ALLOW_IPS` | `*` | Proxy IPs uvicorn trusts for the real client IP |

> Production must run uvicorn with `--proxy-headers --forwarded-allow-ips`
> (already in the Dockerfile) so rate limits key on the real client IP and not a
> spoofable header. Narrow `FORWARDED_ALLOW_IPS` to the proxy CIDR if the
> container is reachable directly.

## Granting extra quota (until billing exists)

Add a row to `ai_quota_grants` (`AIQuotaGrantModel`). It supports per-feature or
all-feature grants, a validity window, and a reason:

```python
session.add(AIQuotaGrantModel(
    user_id=user_id,
    feature=None,              # None = applies to every AI feature
    daily_extra_units=20,      # added on top of AI_BASE_DAILY_LIMIT
    ends_at=datetime.utcnow() + timedelta(days=30),
    reason="early_supporter",
))
```

When billing is added, map the user's plan to a base limit in
`AIUsageService.resolve_base_daily_limit()` — the single seam for plan tiers.
Everything downstream already composes that base with active grants.
