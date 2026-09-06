# Application status: one operation, one history

An application's status used to be assignable from anywhere, and three places
did. Two of them also wrote an event and bumped the company's daily counters;
the third — sharing interview availability — just set the attribute. So an
application could sit at INTERVIEW while its history said IN_REVIEW and the
company dashboard had never counted the move.

## The contract

`ApplicationService.transition_status()` is the only way a status changes.

```python
changed = await application_service.transition_status(
    application,
    to_status=ApplicationStatus.INTERVIEW,
    actor=TransitionActor(recruiter_id=recruiter.id),
)
```

In one transaction it writes: the new status, an `application_status_events`
row (with the actor), and the company's daily counters. It returns `False` and
writes nothing when the application is already in that status, so a replayed
command — a double-clicked button, a retried request — is not a second event.

Callers **lock first**: `await application_service.lock_application(id)` takes a
row lock before the current status is read. Without it two requests both read
"applied" and both write an event for one change. There are no row locks on
SQLite, so that guarantee is only proven in the PostgreSQL lane
(`tests/integration/test_application_transitions_pg.py`).

`TransitionActor` carries who did it — a student (`user_id`) or a recruiter
(`recruiter_id`). Permissions did not change: students still change their own
applications, recruiters still change their company's.

## Three sources, one meaning

| Source | Role |
|---|---|
| `applications.status` | the current state; what the API returns |
| `application_status_events` | the authoritative history, **from the cut-off** |
| `application_daily_aggregates` | a projection of the events, for dashboards |

The counters are applied with `INSERT ... ON CONFLICT DO UPDATE` and SQL-side
addition. Read-modify-write lost increments (two writers both read 4, both wrote
5) and could collide creating the day's first row, turning an analytics update
into a failed request.

## The cut-off

Events are complete only from the deploy of this change onwards. Before it,
transitions made by sharing interview availability wrote nothing, so the log
undercounts INTERVIEW entries and the counters of those days are *more* correct
than a replay of the log would be.

`rebuild_daily_aggregates(company_id=..., since=...)` therefore takes an explicit
`since` and never runs on its own. Rebuilding a day replaces its counters with
what the events say; rebuilding across the pre-cut-off period would replace
correct numbers with an undercount. Use it from the cut-off date forward, or to
repair a specific day.

## Enums

`ApplicationStatus` and `ApplicationMatchStrength` are declared once, in
`app/models/applicationModel.py`, and re-exported by `app/schemas/
applicationSchema.py`. They used to be declared in both, so a value could be
valid in the API and unknown to the column with nothing failing until a request
reached the database.
