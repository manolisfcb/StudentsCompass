"""TASK-055 — the parts of the deployment story that are checkable from here.

Most of that task is provisioning, and provisioning is verified against the
project (`infra/gcp/99-verify.sh`). Three of its claims are not about Google at
all, though — they are about files in this repository — and those are asserted
here so they cannot quietly stop being true:

* no service-account JSON key is committed, ever;
* the frontend image is built without secrets in it;
* the compose stack's development credentials are visibly development ones.

A test that needed a cloud project would be skipped in CI and would therefore
guard nothing. These run in the fast lane.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_DOCKERFILE = REPO_ROOT / "frontend" / "Dockerfile"
BACKEND_DOCKERFILE = REPO_ROOT / "backend" / "Dockerfile"
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
INFRA = REPO_ROOT / "infra" / "gcp"

#: The shape of a Google service-account key file. Finding one of these in the
#: tree means someone took the shortcut Workload Identity Federation exists to
#: make unnecessary.
SERVICE_ACCOUNT_KEY_MARKERS = ('"type": "service_account"', '"private_key":')

SKIPPED_DIRECTORIES = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build",
    "htmlcov", ".pytest_cache", ".mypy_cache", ".ruff_cache",
}


def _tracked_text_files():
    for path in REPO_ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIPPED_DIRECTORIES for part in path.parts):
            continue
        if path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf",
                                   ".woff", ".woff2", ".ttf", ".zip", ".gz", ".db"}:
            continue
        try:
            yield path, path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


class TestNoServiceAccountKeys:
    def test_no_service_account_key_is_committed(self):
        """The acceptance criterion, as a test rather than as a promise.

        A JSON key does not expire, cannot be scoped to a repository and works
        from anywhere. WIF removes the need for one; this makes sure nobody
        adds one back because it was quicker on a Friday.
        """
        offenders = [
            str(path.relative_to(REPO_ROOT))
            for path, text in _tracked_text_files()
            # This file names the markers in order to look for them, so it is
            # the one place they are allowed to appear.
            if path != Path(__file__).resolve()
            and all(marker in text for marker in SERVICE_ACCOUNT_KEY_MARKERS)
        ]

        assert offenders == [], f"service-account key material found in: {offenders}"

    def test_the_provisioning_scripts_never_read_a_secret_value(self):
        """CI wires references; it does not read values.

        `gcloud secrets versions access` is the command that prints a secret.
        It must not appear in anything automated: a deploy pipeline that can
        read production secrets is a deploy pipeline whose logs are a liability.
        """
        offenders = []
        for script in sorted(INFRA.glob("*.sh")):
            text = script.read_text(encoding="utf-8")
            if "secrets versions access" in text:
                offenders.append(script.name)

        assert offenders == [], f"these scripts read secret values: {offenders}"


class TestFrontendImageCarriesNoSecrets:
    def test_the_runtime_stage_copies_only_the_bundle_and_the_nginx_config(self):
        """§11: the frontend image contains configuration, never credentials."""
        content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
        runtime_stage = content.split("AS runtime", 1)[1]

        copies = re.findall(r"^COPY\s+(.+)$", runtime_stage, re.M)

        assert copies, "the runtime stage copies nothing at all — check the Dockerfile"
        for copied in copies:
            assert (
                "nginx.conf" in copied or "/build/dist" in copied
            ), f"unexpected COPY into the frontend runtime image: {copied}"

    def test_the_frontend_build_takes_no_secret_arguments(self):
        """A build ARG ends up in the image's history, readable by anyone who pulls it.

        The API origin reaches Nginx through envsubst at container start, which
        is why nothing here needs to be baked in.
        """
        content = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")
        declared = re.findall(r"^(?:ARG|ENV)\s+([A-Z0-9_]+)", content, re.M)

        forbidden = re.compile(
            r"SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE|API_KEY|ACCESS_KEY", re.I
        )
        offenders = [name for name in declared if forbidden.search(name)]

        assert offenders == [], f"secret-shaped build variables in the frontend image: {offenders}"

    def test_the_backend_image_bakes_in_no_credentials(self):
        content = BACKEND_DOCKERFILE.read_text(encoding="utf-8")
        declared = re.findall(r"^(?:ARG|ENV)\s+([A-Z0-9_]+)", content, re.M)

        forbidden = re.compile(
            r"SECRET|PASSWORD|TOKEN|CREDENTIAL|PRIVATE|API_KEY|ACCESS_KEY", re.I
        )
        offenders = [name for name in declared if forbidden.search(name)]

        assert offenders == [], f"secret-shaped variables in the backend image: {offenders}"


class TestComposeCredentialsAreVisiblyLocal:
    def test_every_literal_credential_in_compose_says_it_is_not_for_deployment(self):
        """The compose file holds working values on purpose — and only these.

        A local stack needs a signing key and a task secret to run at all. The
        risk is not that they exist, it is that one of them looks plausible
        enough to be copied into a deployment. So each one has to say what it is
        in the value itself, where it cannot be separated from it.
        """
        content = COMPOSE_FILE.read_text(encoding="utf-8")
        credential_lines = [
            line.strip()
            for line in content.splitlines()
            if re.search(r"^\s*(SECRET_KEY|INTERNAL_TASKS_SHARED_SECRET):", line)
        ]

        assert credential_lines, "expected the compose stack to declare local credentials"
        for line in credential_lines:
            assert "not-for-deployment" in line, (
                f"local credential does not mark itself as local: {line}"
            )

    def test_the_provisioning_config_example_holds_no_credentials(self):
        example = (INFRA / "config.env.example").read_text(encoding="utf-8")

        forbidden = re.compile(r"(SECRET|PASSWORD|TOKEN|PRIVATE_KEY)\s*=", re.I)

        assert not forbidden.search(example)

    def test_the_real_provisioning_config_is_ignored_by_git(self):
        ignored = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")

        assert "infra/gcp/config.env" in ignored


class TestCleanupPolicyKeepsRollbacksPossible:
    def test_the_registry_keeps_more_images_than_anyone_rolls_back_through(self):
        """A Cloud Run revision pins an image digest.

        Deleting the image makes its revision unbootable, so an aggressive
        cleanup policy silently removes the ability to roll back — which is
        discovered at the worst possible moment.
        """
        policy = json.loads((INFRA / "cleanup-policy.json").read_text(encoding="utf-8"))
        keep = [rule for rule in policy if rule["action"]["type"] == "Keep"]

        assert keep, "the policy must keep recent releases"
        assert keep[0]["mostRecentVersions"]["keepCount"] >= 10
