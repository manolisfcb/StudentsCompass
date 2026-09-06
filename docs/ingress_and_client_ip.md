# Ingress and client IP resolution

Every per-IP limit in the app (request rate limits in
`app/middleware/rate_limit.py`, the AI per-IP limit in
`app/services/ai/aiRequestRateLimitService.py`) is only as good as the answer to
one question: **which address is the client?** That answer has exactly one
definition, `resolve_client_ip()`, driven by one setting.

## `TRUSTED_PROXY_IPS`

Declares which *immediate peers* — the address on the other end of the TCP
connection — are allowed to speak for the client through `X-Forwarded-For`.

| Value | Meaning |
|---|---|
| `private` (default) | Trust loopback, RFC1918, CGNAT (`100.64/10`), link-local and IPv6 ULA peers. A managed load balancer (Cloud Run, Fly, ECS, an ingress controller) reaches the container from such an address; a request that arrives *directly* from the internet has a public peer and therefore cannot declare its own IP. |
| `none` / empty | Trust nobody: the socket peer is always the client. Correct when nothing fronts the app. |
| `10.1.2.0/24, 198.51.100.4` | Comma-separated IPs and/or CIDRs. The tightest option — use it once the balancer's real egress range is known. |
| `*` | Trust any peer. **Only** correct when the container is provably unreachable except through the proxy; otherwise anyone can hand themselves a fresh rate-limit bucket per request by inventing a header. |

`FORWARDED_ALLOW_IPS` is the previous name and is still read, so a deployment
that already exports it keeps working. Unparseable entries are ignored — a typo
narrows trust, it never widens it.

### How the header is read

When the peer is trusted, the chain is walked **right to left**: each proxy
appends the address it actually saw, so the rightmost entry that is not itself a
trusted proxy is the client. Anything further left was written by the caller and
is not evidence. When the peer is not trusted, the header is not read at all.

## Why uvicorn no longer parses proxy headers

The Dockerfile previously ran uvicorn with `--proxy-headers
--forwarded-allow-ips "*"`, which rewrote `request.client.host` from
`X-Forwarded-For` for *any* peer before the app could see who really connected.
That put the trust decision in two places and defaulted the outer one to "trust
everyone". The container now runs uvicorn plain and the app resolves the client
itself, so `TRUSTED_PROXY_IPS` is the single source of truth.

Nothing else depended on uvicorn's proxy handling: public absolute URLs come
from `APP_BASE_URL`/`PUBLIC_APP_ORIGIN` (`app/app.py:_get_public_base_url`) and
the admin same-origin check reads `X-Forwarded-Proto`/`X-Forwarded-Host` itself
(`app/routes/adminRoute.py`).

## Before closing the configuration

`private` is a safe default, not a verified one. For the real deployment:

1. Confirm whether the container can be reached without going through the load
   balancer (a direct hit on the instance/service address). If it can, that path
   must be closed at the platform level — no header policy fixes a service that
   is directly addressable.
2. Read the peer address the platform actually uses and set `TRUSTED_PROXY_IPS`
   to that CIDR.
3. Re-check that limits key on distinct client addresses afterwards: several
   users sharing one bucket (everyone collapsing onto the balancer IP) is as
   much a failure as no limit at all.

## Endpoints covered by per-IP request limits

| Rule key | Paths | Default |
|---|---|---|
| `auth_login` | `/auth/jwt/login`, `/api/v1/auth/company/login` | 8 / 60s |
| `auth_register_burst` | `/api/v1/auth/register`, `/api/v1/auth/company/register` | 5 / 3600s |
| `auth_register_daily` | same as above | 5 / day |
| `auth_recovery` | `forgot-password`, `reset-password`, `request-verify-token` for both identities | 5 / 3600s |
| `admin_api` | `/api/v1/admin/*` | 120 / 60s |
| `admin_pages` | `/admin`, `/admin/login*` | 60 / 60s |

Both identities — students and company recruiters — share a bucket per rule, on
purpose: the thing being rationed is "credential attempts from this IP" and
"accounts created from this IP", and a company account is an account.
