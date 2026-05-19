"""Shared fixtures for integration tests.

Integration tests trigger DAGs on the local Airflow REST API and inspect
Unity Catalog OSS + Marquez over HTTP. All endpoints are resolved from
env vars with local-docker-compose defaults, so the same suite works on
laptops and CI runners.

If ANY of the three endpoints (Airflow, UC, Marquez) is not answering
HTTP, every integration test in the layer modules is skipped with a
single, named reason. The probe is HTTP-level (not TCP) so an unrelated
process binding the port does not yield a false-pass skip.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

import pytest
import requests


# Endpoint defaults align with patient_360/docker-compose.yml. Tests
# read everything from env so CI / alternate stacks can override.
_AIRFLOW_API_DEFAULT = "http://localhost:8088/api/v1"
_UC_URI_DEFAULT = "http://localhost:8080/api/2.1/unity-catalog"
_MARQUEZ_API_DEFAULT = "http://localhost:5001/api/v1"


@dataclass(frozen=True)
class StackEndpoints:
    airflow_api: str
    airflow_user: str
    airflow_password: str
    uc_uri: str
    uc_catalog: str
    marquez_api: str
    marquez_namespace: str
    # Per-layer DAG IDs + UC schemas (lookup by upper-case layer name).
    bronze_dag_id: str
    uc_bronze_schema: str

    def airflow_auth(self) -> tuple[str, str]:
        return (self.airflow_user, self.airflow_password)

    def dag_id_for(self, layer: str) -> str:
        layer = layer.lower()
        if layer == "bronze":
            return self.bronze_dag_id
        raise KeyError(f"No DAG ID configured for layer {layer!r}")

    def uc_schema_for(self, layer: str) -> str:
        layer = layer.lower()
        if layer == "bronze":
            return self.uc_bronze_schema
        raise KeyError(f"No UC schema configured for layer {layer!r}")


@pytest.fixture(scope="session")
def stack() -> StackEndpoints:
    return StackEndpoints(
        airflow_api=os.environ.get("AIRFLOW_API", _AIRFLOW_API_DEFAULT).rstrip("/"),
        airflow_user=os.environ.get("AIRFLOW_USER", "airflow"),
        airflow_password=os.environ.get("AIRFLOW_PASSWORD", "airflow"),
        uc_uri=os.environ.get("UC_URI", _UC_URI_DEFAULT).rstrip("/"),
        uc_catalog=os.environ.get("UC_CATALOG", "unity"),
        marquez_api=os.environ.get("MARQUEZ_API", _MARQUEZ_API_DEFAULT).rstrip("/"),
        marquez_namespace=os.environ.get("MARQUEZ_NAMESPACE", "patient_360"),
        bronze_dag_id=os.environ.get("BRONZE_DAG_ID", "patient360_hourly_v1"),
        uc_bronze_schema=os.environ.get("UC_BRONZE_SCHEMA", "bronze"),
    )


def _probe(url: str, auth: Optional[tuple[str, str]] = None, timeout: float = 3.0) -> Optional[str]:
    """Return None on healthy HTTP (200 or 401 — auth-protected is fine),
    otherwise a short string describing the failure suitable for a skip
    message."""
    try:
        resp = requests.get(url, auth=auth, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        return f"{url} unreachable ({type(exc).__name__})"
    if resp.status_code in (200, 401):
        return None
    return f"{url} returned HTTP {resp.status_code}"


@pytest.fixture(scope="session", autouse=True)
def _require_stack(stack: StackEndpoints) -> None:
    """HTTP-probe every required endpoint. Skip the whole integration
    suite (with a precise reason) if any probe fails."""
    failures: list[str] = []

    af = _probe(f"{stack.airflow_api}/version", auth=stack.airflow_auth())
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
