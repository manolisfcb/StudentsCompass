# AI cost & abuse controls

This app makes paid LLM calls (Gemini) from two features: CV job-search keyword
extraction and the resume course-audit. The controls below cap what those can
cost, per user and globally, even under hundreds of concurrent users or abuse.

## Layers of protection

1. **Per-user daily quota (atomic).** `AIUsageService.reserve()` claims a slot in
   a shared atomic counter *before* any LLM spend, so concurrent requests cannot
   race past the limit. The durable ledger (`AIUsageEventModel`) is the source of
   truth; the counter is seeded from it so a counter reset never hands back
   already-spent quota. See [the reservation cycle](#the-reservation-cycle) for
   what happens to a slot after it is claimed.
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

## The reservation cycle

A reserved slot is a row in `ai_usage_events`, not just a number in a counter,
and it ends in exactly one state:

| `status` | Means | Counts against the daily limit |
|---|---|---|
| `reserved` | claimed before the provider call, lease running | yes, while `expires_at` is in the future |
| `committed` | a result was produced and charged | yes |
| `released` | handed back — no result | no |
| `expired` | nobody settled it and the lease ran out | no |
| `superseded` | duplicate charge for a reference already charged, kept as evidence | no |

Three consequences worth knowing:

* **A charge is idempotent per result.** The partial unique index
  `uq_ai_usage_events_reference` allows one *committed* row per
  `(reference_type, reference_id)`, so a replayed background task or a retried
  request records the same analysis once. The loser of that race releases its
  own reservation instead of stranding it.
* **A dead process cannot cost a user their day.** `RESERVATION_LEASE_SECONDS`
  (15 min) bounds how long an unsettled claim counts. An expired reservation
  stops counting by predicate — no repair job — and the next `reserve()` by the
  same user reclaims it and credits the shared counter back, exactly once.
* **Provider spend and user entitlement are different things.** A failed attempt
  releases the user's slot (`released_after_provider_attempt` records that an
  attempt did happen); the money side is the global attempt ceiling in layer 2,
  which counts every attempt including retries.

The ledger is the only authority for "how much has this user used today".
Historical rows from before it existed — `job_analysis` and
`resume_course_evaluations` — were reconciled into it **by identity** by the
`d1c7e3a95b48` migration, one ledger row per legacy attempt, preserving the
original timestamps. The previous read took `max(ledger_count, legacy_count)`,
which could not tell a missing ledger row from a genuinely cheaper day, and
charged for `job_analysis` rows whose slot had been explicitly released (a cache
hit, an unreadable CV). `AIUsageService.legacy_parity_gaps()` re-runs the
comparison at any time; an empty result is the invariant.

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
| `RECOVERY_RATE_LIMIT_MAX` / `_WINDOW_SECONDS` | `5` / `3600` | forgot/reset password + verify-token per IP (both identities) |
| `TRUSTED_PROXY_IPS` | `private` | Peers allowed to declare the client IP via `X-Forwarded-For` (was `FORWARDED_ALLOW_IPS`, still read) |

> Rate limits are only as good as the client IP they key on. `TRUSTED_PROXY_IPS`
> decides which immediate peer may speak for the client; the default trusts
> private/loopback peers (a managed load balancer) and ignores the header on a
> direct hit from the internet. Narrow it to the balancer CIDR once the real
> ingress is known — see [ingress_and_client_ip.md](ingress_and_client_ip.md).

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
