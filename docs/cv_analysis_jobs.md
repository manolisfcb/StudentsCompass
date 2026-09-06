# CV analysis jobs

`POST /api/v1/jobs/keywords/analyze` does not analyse anything. It puts a row in
`job_analysis` and returns a `job_id` the browser polls on
`GET /api/v1/jobs/keywords/{job_id}`. That contract is unchanged; what follows is
how the row gets processed and what happens when nobody finishes it.

## The queue is the table

`job_analysis` **is** the queue. It is small, the API already polls it, and its
row is already the thing the user is waiting for — a second queue in Redis would
just be a second place that can disagree about the same job.

| Column | Purpose |
|---|---|
| `status` | `PENDING` → `PROCESSING` → `COMPLETED` / `FAILED` (unchanged) |
| `attempts` | how many times the job has been claimed; bounds retries |
| `lease_expires_at` | until when the current worker owns it; `NULL` when terminal |
| `provider_attempted_at` | stamped immediately before the Gemini call |

Two indexes carry the rules:

* `uq_job_analysis_active_per_resume` — unique on `(user_id, resume_id)` **where**
  `status IN ('PENDING','PROCESSING')`. One live analysis per CV, decided by the
  database. Checking "is one running?" and then inserting is two statements, and
  two simultaneous requests both got past the first one; now the loser reads the
  winner's job and both poll the same `job_id`.
* `ix_job_analysis_active_lease` — the runner's due-work scan touches only
  unfinished rows.

## Claiming

Claiming is one conditional UPDATE: `PENDING`, or `PROCESSING` with a lease that
has run out, becomes `PROCESSING` with a fresh lease and `attempts + 1`. Whoever
gets `rowcount == 1` owns the job.

That is what makes it safe for two dispatchers to reach for the same row. Both
run on purpose:

* the request's `BackgroundTasks` — keeps the current latency, work starts
  immediately;
* `CVAnalysisRunner` (`app/services/ai/cvAnalysisRunner.py`) — a loop started in
  the app lifespan, with its own session per job and a clean shutdown. This is
  the half that survives the request, and the process.

## Recovery, and the one thing it will not do

A worker that dies leaves a lease behind. When it expires the runner decides,
and the decision turns on `provider_attempted_at`:

| State of the abandoned job | Outcome |
|---|---|
| provider never called, `attempts < 3` | back to `PENDING`, someone claims it again |
| provider never called, `attempts >= 3` | `FAILED`, explicitly: it keeps dying |
| **provider already called** | `FAILED`, explicitly — never retried |

The last row is the rule that outranks "make it recover". Once the request to
Gemini went out, the app cannot know whether it completed or what it cost. Re-
running it would be spending money on a guess, so the job is failed with a
message that says what happened and the user starts a new analysis deliberately.

Re-running a job is idempotent in the accounting sense too: the usage ledger is
unique per `job_analysis` id (see [ai_cost_controls.md](ai_cost_controls.md)), so
a replayed job records one charge, not two. A job the runner adopts arrives
without the reservation the original request held, so it claims quota itself
immediately before the call — over quota fails the job instead of spending.

## Failure modes this removes

* **A restart used to block the CV forever.** A row stuck on `PROCESSING` is also
  how the API decides to refuse a new analysis, so the bug fed itself until
  someone edited the row by hand. Leases end that.
* **Two POSTs used to start two analyses**, both spending, for one CV.
* **A job could finish with no charge, or be charged twice**, depending on which
  path it took.

## Operational notes

* `JOB_LEASE_SECONDS = 300` and `MAX_JOB_ATTEMPTS = 3` live in
  `app/services/ai/cvAnalysisService.py`; `POLL_INTERVAL_SECONDS = 5` in the
  runner. None are env vars yet — change them there.
* The runner is per-process. With several replicas each runs one, which is fine:
  claiming is what keeps them from colliding, not counting them.
* The browser gives up polling after 20 tries (60 s) and says so, but the job
  keeps running and its result is stored; the next `analyze` call returns the
  cached analysis rather than spending again.
