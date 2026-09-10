"""How an outbox row reaches a worker.

Three transports, and the differences between them are deployment facts, not
behaviour: the row, the endpoint and the job's own state machine are identical
in all three.

* **Cloud Tasks** (production). The queue holds the task, retries it with its
  own backoff, and mints an OIDC token so the endpoint can prove who called it.
* **HTTP** (compose, dev). The worker posts the internal endpoint itself,
  carrying a shared secret. It has no queue behind it, so the outbox's own
  backoff is what makes it durable.
* **Disabled** (default, and what tests get). Refuses rather than inventing a
  destination — a deployment that has not been configured must fail visibly.

Cloud Tasks is reached over its REST API with credentials from
``google.auth``, which is already a dependency. The ``google-cloud-tasks``
client would add one for a single POST.
"""
from __future__ import annotations

import json
import logging
from typing import Protocol

import httpx

from app.config import (
    CLOUD_TASKS_QUEUE,
    CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL,
    INTERNAL_TASKS_AUDIENCE,
    INTERNAL_TASKS_BASE_URL,
    INTERNAL_TASKS_SHARED_SECRET,
    TASK_DISPATCH_TRANSPORT,
)
from app.models.taskOutboxModel import TASK_CV_ANALYSIS, TaskOutboxModel

LOGGER = logging.getLogger(__name__)

CLOUD_TASKS_ENDPOINT = "https://cloudtasks.googleapis.com/v2"
CLOUD_TASKS_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
#: A dispatch is a POST that returns quickly; the work itself is bounded by the
#: job's lease, not by this.
DISPATCH_TIMEOUT_SECONDS = 10.0

#: The header the HTTP transport uses instead of an OIDC token.
SHARED_SECRET_HEADER = "X-Internal-Task-Secret"


class TransportNotConfigured(RuntimeError):
    """Delivery was attempted with no destination configured."""


class TaskTransport(Protocol):
    async def deliver(self, row: TaskOutboxModel) -> None: ...


def task_path(row: TaskOutboxModel) -> str:
    """The internal URL for one outbox row."""
    if row.task_type != TASK_CV_ANALYSIS:
        raise TransportNotConfigured(f"No route is defined for task type {row.task_type!r}")
    job_id = (row.payload or {}).get("job_id")
    if not job_id:
        raise TransportNotConfigured("The dispatch carries no job_id")
    return f"/internal/tasks/cv-analyses/{job_id}"


class DisabledTransport:
    """The default. Says so instead of guessing a destination."""

    async def deliver(self, row: TaskOutboxModel) -> None:
        raise TransportNotConfigured(
            "TASK_DISPATCH_TRANSPORT is disabled; no dispatch destination is configured."
        )


class HttpTransport:
    """POST the internal endpoint directly, with a shared secret.

    For compose and local development. The secret is not an identity — it says
    "whoever holds this string" — which is why the endpoint refuses it when
    ``ENV=production``.
    """

    def __init__(self, base_url: str, secret: str, *, client: httpx.AsyncClient | None = None):
        if not base_url:
            raise TransportNotConfigured("INTERNAL_TASKS_BASE_URL is not set")
        self._base_url = base_url.rstrip("/")
        self._secret = secret
        self._client = client

    async def deliver(self, row: TaskOutboxModel) -> None:
        url = f"{self._base_url}{task_path(row)}"
        headers = {SHARED_SECRET_HEADER: self._secret} if self._secret else {}
        if self._client is not None:
            response = await self._client.post(url, headers=headers)
        else:
            async with httpx.AsyncClient(timeout=DISPATCH_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers)
        response.raise_for_status()


class CloudTasksTransport:
    """Create one Cloud Tasks HTTP task carrying an OIDC token.

    The token is minted by Cloud Tasks for ``service_account_email``, so the
    endpoint authenticates the *queue's identity* rather than a bearer string
    that anyone who reads a log could replay.

    ``taskId`` is derived from the outbox row's dedupe key, which gives the
    queue the same de-duplication the table has: a second create for the same
    key is refused with ``ALREADY_EXISTS``, and that is a success here, not an
    error to retry.
    """

    def __init__(
        self,
        *,
        queue: str,
        base_url: str,
        service_account_email: str,
        audience: str,
        credentials=None,
        client: httpx.AsyncClient | None = None,
    ):
        missing = [
            name
            for name, value in (
                ("CLOUD_TASKS_QUEUE", queue),
                ("INTERNAL_TASKS_BASE_URL", base_url),
                ("CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL", service_account_email),
            )
            if not value
        ]
        if missing:
            raise TransportNotConfigured(f"Cloud Tasks needs {', '.join(missing)}")
        self._queue = queue
        self._base_url = base_url.rstrip("/")
        self._service_account_email = service_account_email
        self._audience = audience or self._base_url
        self._credentials = credentials
        self._client = client

    def _access_token(self) -> str:
        credentials = self._credentials
        if credentials is None:
            import google.auth  # imported lazily: only production needs it

            credentials, _ = google.auth.default(scopes=[CLOUD_TASKS_SCOPE])
            self._credentials = credentials
        if not getattr(credentials, "valid", False):
            from google.auth.transport.requests import Request

            credentials.refresh(Request())
        return credentials.token

    async def deliver(self, row: TaskOutboxModel) -> None:
        url = f"{CLOUD_TASKS_ENDPOINT}/{self._queue}/tasks"
        body = {
            # Named after the dedupe key so the queue refuses a duplicate for us.
            "task": {
                "name": f"{self._queue}/tasks/{_task_id(row)}",
                "httpRequest": {
                    "url": f"{self._base_url}{task_path(row)}",
                    "httpMethod": "POST",
                    "oidcToken": {
                        "serviceAccountEmail": self._service_account_email,
                        "audience": self._audience,
                    },
                },
            }
        }
        headers = {
            "Authorization": f"Bearer {self._access_token()}",
            "Content-Type": "application/json",
        }
        if self._client is not None:
            response = await self._client.post(url, headers=headers, content=json.dumps(body))
        else:
            async with httpx.AsyncClient(timeout=DISPATCH_TIMEOUT_SECONDS) as client:
                response = await client.post(url, headers=headers, content=json.dumps(body))
        if response.status_code == 409:
            # ALREADY_EXISTS: the task is in the queue. Nothing to retry.
            LOGGER.info("Cloud Task for %s already existed", row.dedupe_key)
            return
        response.raise_for_status()


def _task_id(row: TaskOutboxModel) -> str:
    """A queue-safe id derived from the dedupe key.

    Cloud Tasks accepts letters, digits, hyphens and underscores, so the colon
    in ``cv_analysis:<uuid>`` is replaced rather than the id being random —
    a random one would let a retry create a second task.
    """
    return row.dedupe_key.replace(":", "-")


def build_transport() -> TaskTransport:
    """The transport this deployment is configured for."""
    kind = TASK_DISPATCH_TRANSPORT
    if kind == "cloud_tasks":
        return CloudTasksTransport(
            queue=CLOUD_TASKS_QUEUE,
            base_url=INTERNAL_TASKS_BASE_URL,
            service_account_email=CLOUD_TASKS_SERVICE_ACCOUNT_EMAIL,
            audience=INTERNAL_TASKS_AUDIENCE,
        )
    if kind == "http":
        return HttpTransport(INTERNAL_TASKS_BASE_URL, INTERNAL_TASKS_SHARED_SECRET)
    return DisabledTransport()
