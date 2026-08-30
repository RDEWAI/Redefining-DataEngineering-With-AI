"""Shared fixtures for integration tests.

Integration tests trigger DAGs on the local Airflow REST API and inspect
Unity Catalog OSS + Marquez over HTTP. All endpoints are resolved from
env vars with local-docker-compose defaults, so the same suite works on
laptops and CI runners.

Airflow 3.x (SimpleAuthManager) exposes a JWT-only REST API at
``/api/v2`` on host port 8081. Basic-auth tuples return HTTP 401; instead
a bearer token is minted once per session from ``POST /auth/token`` (the
server root, NOT under ``/api/v2``) and attached as an
``Authorization: Bearer <token>`` header on every authenticated call. The
token endpoint answers **201 Created** on Airflow 3.2.1 (some builds
return 200), so the token fixture accepts EITHER status.

If ANY of the three endpoints (Airflow, UC, Marquez) is not answering
HTTP, every integration test in the layer modules is skipped with a
single, named reason. The probe is HTTP-level (not TCP) so an unrelated
process binding the port does not yield a false-pass skip. The Airflow
health probe hits ``/api/v2/monitor/health`` which is unauthenticated on
Airflow 3.x and returns 200 when the API server is ready.
"""

from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import pytest
import requests

# Endpoint defaults align with patient_360/docker-compose.yml. Tests
# read everything from env so CI / alternate stacks can override.
# Airflow 3.x: host port 8081 -> container 8080, REST under /api/v2.
_AIRFLOW_API_DEFAULT = "http://localhost:8081/api/v2"
_UC_URI_DEFAULT = "http://localhost:8080/api/2.1/unity-catalog"
_MARQUEZ_API_DEFAULT = "http://localhost:5001/api/v1"


def _derive_auth_url(airflow_api: str) -> str:
    """Derive the token endpoint from the API base.

    Airflow 3.x mints JWTs at the server root ``/auth/token`` (NOT under
    ``/api/v2``). Strip a trailing ``/api/v2`` (or ``/api/vN``) segment
    from the API base and append ``/auth/token``.
    """
    base = airflow_api.rstrip("/")
    for suffix in ("/api/v2", "/api/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base.rstrip('/')}/auth/token"


@dataclass(frozen=True)
class StackEndpoints:
    airflow_api: str
    airflow_user: str
    airflow_password: str
    airflow_auth_url: str
    uc_uri: str
    uc_catalog: str
    marquez_api: str
    marquez_namespace: str
    # Per-layer DAG IDs + UC schemas (lookup by upper-case layer name).
    bronze_dag_id: str
    uc_bronze_schema: str
    gold_dag_id: str
    uc_gold_schema: str

    def dag_id_for(self, layer: str) -> str:
        layer = layer.lower()
        if layer == "bronze":
            return self.bronze_dag_id
        if layer == "gold":
            return self.gold_dag_id
        raise KeyError(f"No DAG ID configured for layer {layer!r}")

    def uc_schema_for(self, layer: str) -> str:
        layer = layer.lower()
        if layer == "bronze":
            return self.uc_bronze_schema
        if layer == "gold":
            return self.uc_gold_schema
        raise KeyError(f"No UC schema configured for layer {layer!r}")


@pytest.fixture(scope="session")
def stack() -> StackEndpoints:
    airflow_api = os.environ.get("AIRFLOW_API", _AIRFLOW_API_DEFAULT).rstrip("/")
    return StackEndpoints(
        airflow_api=airflow_api,
        airflow_user=os.environ.get("AIRFLOW_USER", "admin"),
        airflow_password=os.environ.get("AIRFLOW_PASSWORD", "admin"),
        airflow_auth_url=os.environ.get(
            "AIRFLOW_AUTH_URL", _derive_auth_url(airflow_api)
        ).rstrip("/"),
        uc_uri=os.environ.get("UC_URI", _UC_URI_DEFAULT).rstrip("/"),
        uc_catalog=os.environ.get("UC_CATALOG", "unity"),
        marquez_api=os.environ.get("MARQUEZ_API", _MARQUEZ_API_DEFAULT).rstrip("/"),
        marquez_namespace=os.environ.get("MARQUEZ_NAMESPACE", "patient_360"),
        bronze_dag_id=os.environ.get("BRONZE_DAG_ID", "patient360_hourly_v1"),
        uc_bronze_schema=os.environ.get("UC_BRONZE_SCHEMA", "bronze"),
        gold_dag_id=os.environ.get("GOLD_DAG_ID", "patient360_hourly_v1"),
        uc_gold_schema=os.environ.get("UC_GOLD_SCHEMA", "gold"),
    )


@pytest.fixture(scope="session")
def airflow_token(stack: StackEndpoints) -> str:
    """Mint a JWT once per session via ``POST {AIRFLOW_AUTH_URL}``.

    Airflow 3.x SimpleAuthManager returns ``{"access_token": "<jwt>"}``.
    The token endpoint answers **201 Created** on Airflow 3.2.1 (some
    builds return 200), so BOTH statuses are accepted as success — a
    200-only check would skip every integration test (no token → no DAG
    trigger) on a 201-returning stack. Basic-auth tuples are rejected
    (401), so every authenticated REST call must carry the bearer header
    built from this token.
    """
    try:
        resp = requests.post(
            stack.airflow_auth_url,
            json={"username": stack.airflow_user, "password": stack.airflow_password},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        pytest.skip(
            f"Airflow token endpoint {stack.airflow_auth_url} unreachable "
            f"({type(exc).__name__}); bring up the stack with "
            f"`make dev-up && make dev-bootstrap`."
        )
    if resp.status_code not in (200, 201):
        pytest.skip(
            f"Airflow token endpoint {stack.airflow_auth_url} returned "
            f"HTTP {resp.status_code} (expected 200 or 201): {resp.text[:200]}"
        )
    token = resp.json().get("access_token")
    if not token:
        pytest.fail(
            f"Airflow token endpoint {stack.airflow_auth_url} returned no "
            f"access_token: {resp.text[:200]}"
        )
    return token


@pytest.fixture(scope="session")
def airflow_headers(airflow_token: str) -> dict[str, str]:
    """Bearer auth header for every authenticated Airflow v2 REST call."""
    return {"Authorization": f"Bearer {airflow_token}"}


def _probe(url: str, timeout: float = 3.0) -> str | None:
    """Return None on healthy HTTP (200), otherwise a short string
    describing the failure suitable for a skip message."""
    try:
        resp = requests.get(url, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return f"{url} unreachable ({type(exc).__name__})"
    if resp.status_code == 200:
        return None
    return f"{url} returned HTTP {resp.status_code}"


@pytest.fixture(autouse=True)
def _require_stack(request, stack: StackEndpoints) -> None:
    """HTTP-probe every required endpoint. Skip the whole integration
    suite (with a precise reason) if any probe fails.

    The Airflow probe hits ``/api/v2/monitor/health`` — unauthenticated on
    Airflow 3.x, returns 200 when the API server is ready. UC and Marquez
    probes are unchanged.

    Tests marked ``local_spark`` are self-contained local-Spark smokes that
    need no live Airflow/UC/Marquez stack (e.g. STORY-02-010 AC5 SE
    rule-matching). They opt out of the HTTP probe so they still run on a
    laptop with the docker stack down.
    """
    if request.node.get_closest_marker("local_spark"):
        return

    failures: list[str] = []

    af = _probe(f"{stack.airflow_api}/monitor/health")
    if af:
        failures.append(f"Airflow: {af}")

    uc = _probe(f"{stack.uc_uri}/catalogs")
    if uc:
        failures.append(f"Unity Catalog: {uc}")

    mq = _probe(f"{stack.marquez_api}/namespaces")
    if mq:
        failures.append(f"Marquez: {mq}")

    if failures:
        pytest.skip(
            "Local stack not ready for integration tests — "
            + "; ".join(failures)
            + ". Bring it up with `make dev-up && make dev-bootstrap` and retry."
        )


# ---------------------------------------------------------------------------
# Shared successful-Gold-run fixture (order-independent)
# ---------------------------------------------------------------------------
#
# Every Gold integration test — whether collected first (test_gold_se_evidence)
# or last (test_gold_uc) — must read evidence from ONE and the SAME fresh,
# successful ``patient360_hourly_v1`` run. Independent per-test triggering
# (test_gold_uc) plus independent latest-successful scanning (the se_evidence
# tests) made the suite collection-order dependent: an alphabetically-earlier
# evidence test could pick up a STALE prior run (e.g. ``prestart-*``) that has
# no ``reconciliation_gold`` task and fail.
#
# The ``successful_gold_run`` session fixture removes that coupling:
#   * FAST PATH — reuse the most recent ``state=success`` run if it ended
#     within the reuse window (no new trigger, no 30-min wait).
#   * SLOW PATH — otherwise unpause (if paused) + trigger a fresh run using the
#     same JWT auth + ``logical_date`` contract, then poll to ``success``.
# It returns the run payload (``dag_run_id`` + ``state``) so consumers can both
# assert success (AC1) and address the run's task instances / SE evidence.

_GOLD_REUSE_WINDOW_MINUTES = 45
_GOLD_POLL_INTERVAL_SEC = 10
_GOLD_RUN_TIMEOUT_SEC = 1800


def _parse_airflow_ts(value: str | None) -> datetime | None:
    """Parse an Airflow REST timestamp (ISO-8601, ``Z`` or offset) to aware UTC."""
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _latest_successful_gold_run(
    stack: StackEndpoints, headers: dict[str, str]
) -> dict | None:
    """Most recent ``state=success`` Gold DAG run (JWT-only ``/api/v2``)."""
    dag_id = stack.dag_id_for("gold")
    resp = requests.get(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns",
        params={"state": "success", "order_by": "-end_date", "limit": 10},
        headers=headers,
        timeout=10,
    )
    resp.raise_for_status()
    runs = resp.json().get("dag_runs", [])
    return runs[0] if runs else None


def _unpause_gold_dag(stack: StackEndpoints, headers: dict[str, str]) -> None:
    """Unpause the Gold DAG so a fresh trigger is schedulable (idempotent)."""
    dag_id = stack.dag_id_for("gold")
    requests.patch(
        f"{stack.airflow_api}/dags/{dag_id}",
        params={"update_mask": "is_paused"},
        json={"is_paused": False},
        headers=headers,
        timeout=10,
    )


def _trigger_gold_run(stack: StackEndpoints, headers: dict[str, str]) -> str:
    """Trigger a fresh Gold DAG run; return its run_id. Accepts HTTP 200/201.

    Airflow 3.x ``/api/v2`` requires a timezone-aware ``logical_date``.
    """
    dag_id = stack.dag_id_for("gold")
    run_id = f"integration-{uuid.uuid4().hex[:8]}"
    logical_date = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = requests.post(
        f"{stack.airflow_api}/dags/{dag_id}/dagRuns",
        json={"dag_run_id": run_id, "logical_date": logical_date},
        headers=headers,
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        pytest.fail(
            f"Airflow refused to trigger {dag_id} "
            f"(HTTP {resp.status_code}): {resp.text[:300]}"
        )
    return run_id


def _poll_gold_run(
    stack: StackEndpoints, run_id: str, headers: dict[str, str]
) -> dict:
    """Poll a Gold DAG run to a terminal state or the deadline."""
    dag_id = stack.dag_id_for("gold")
    started = time.monotonic()
    while time.monotonic() - started < _GOLD_RUN_TIMEOUT_SEC:
        resp = requests.get(
            f"{stack.airflow_api}/dags/{dag_id}/dagRuns/{run_id}",
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("state") in ("success", "failed"):
            return payload
        time.sleep(_GOLD_POLL_INTERVAL_SEC)
    pytest.fail(
        f"DAG run {dag_id}/{run_id} did not complete within "
        f"{_GOLD_RUN_TIMEOUT_SEC}s"
    )


@pytest.fixture(scope="session")
def successful_gold_run(
    stack: StackEndpoints, airflow_headers: dict[str, str]
) -> dict:
    """A single SUCCESSFUL ``patient360_hourly_v1`` run shared by all Gold tests.

    Reuses a recent success (ended within ``_GOLD_REUSE_WINDOW_MINUTES``) when
    one exists — the fast path avoids a ~30-min re-trigger. Otherwise unpauses
    and triggers a fresh run, then polls to ``success``. Returns the run payload
    (``dag_run_id`` + ``state``). Guarantees ``state == "success"`` on return.
    """
    latest = _latest_successful_gold_run(stack, airflow_headers)
    if latest is not None:
        ended = _parse_airflow_ts(latest.get("end_date"))
        if ended is not None:
            age = datetime.now(UTC) - ended
            if age <= timedelta(minutes=_GOLD_REUSE_WINDOW_MINUTES):
                return latest

    _unpause_gold_dag(stack, airflow_headers)
    run_id = _trigger_gold_run(stack, airflow_headers)
    payload = _poll_gold_run(stack, run_id, airflow_headers)
    if payload.get("state") != "success":
        pytest.fail(
            f"Fresh Gold DAG run {run_id} ended in state "
            f"{payload.get('state')!r}: {payload}"
        )
    return payload
