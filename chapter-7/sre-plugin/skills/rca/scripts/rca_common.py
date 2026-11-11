"""Shared helpers for the `rca` skill scripts (find_alert / collect_evidence / check_report).

Everything here is read-only: GET-only HTTP, subprocess calls that only read,
and pure parsing. No module-level side effects.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------------
# Endpoints (same defaults + env overrides as patient_360/tests/integration)
# --------------------------------------------------------------------------
AIRFLOW_API_DEFAULT = "http://localhost:8081/api/v2"
UC_URI_DEFAULT = "http://localhost:8080"
MARQUEZ_API_DEFAULT = "http://localhost:5001/api/v1"
HTTP_TIMEOUT = 15


def airflow_api() -> str:
    return os.environ.get("AIRFLOW_API", AIRFLOW_API_DEFAULT).rstrip("/")


def airflow_auth_url() -> str:
    """Airflow 3.x mints JWTs at ``<root>/auth/token`` (not under /api/v2)."""
    explicit = os.environ.get("AIRFLOW_AUTH_URL")
    if explicit:
        return explicit.rstrip("/")
    base = airflow_api()
    for suffix in ("/api/v2", "/api/v1"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
            break
    return f"{base.rstrip('/')}/auth/token"


def uc_uri() -> str:
    return os.environ.get("UC_URI", UC_URI_DEFAULT).rstrip("/")


def marquez_api() -> str:
    return os.environ.get("MARQUEZ_API", MARQUEZ_API_DEFAULT).rstrip("/")


# --------------------------------------------------------------------------
# Workspace discovery (delegates to sre-plugin/scripts/discover_workspace.py)
# --------------------------------------------------------------------------
def _plugin_root() -> Path:
    return Path(__file__).resolve().parents[3]


def discover(start: Path | None = None, workspace_root: Path | None = None):
    helper = _plugin_root() / "scripts" / "discover_workspace.py"
    spec = importlib.util.spec_from_file_location("_sre_discover", helper)
    assert spec and spec.loader
    mod = sys.modules.get("_sre_discover")
    if mod is None:
        mod = importlib.util.module_from_spec(spec)
        sys.modules["_sre_discover"] = mod  # must be registered before exec (dataclasses on 3.14)
        spec.loader.exec_module(mod)
    return mod.discover_workspace(start or Path.cwd(), workspace_root)


# --------------------------------------------------------------------------
# Alert contract + LLD §8.5 classifier
# --------------------------------------------------------------------------
REQUIRED_ALERT_FIELDS = (
    "alert_id",
    "fired_at",
    "env",
    "condition",
    "severity",
    "source",
    "message",
)
OPTIONAL_ALERT_FIELDS = (
    "channel",
    "dag_id",
    "run_id",
    "task_id",
    "try_number",
    "ds",
    "failure_class",
    "response_time",
    # set by utils/alerting.py (DAG callback) and the rca-runner webhook receiver
    "markers",
    "incident_id",
    "incident_url",
    "incident_provider",
    "dedup_key",
)
VALID_SEVERITIES = ("CRITICAL", "WARNING", "INFO")
VALID_SOURCES = ("airflow", "se", "manual")


@dataclass(frozen=True)
class ConditionRule:
    pattern: str
    condition: str
    failure_class: str
    severity: str
    channel: str
    response_time: str
    lld_ref: str = "LLD §8.5"


# Order matters. Explicit markers (SE gate, UC, OOM, import) come first because
# they name the mechanism; the allergy rule comes after them and needs a DQ
# signal (rule id, action_if_failed, dq stage) in addition to the table/task
# name, so an infra failure on `ingest_allergies` is not mislabelled as a DQ
# failure (live RCA 2026-10-15). Mirrors LLD §8.5 (alerting thresholds).
DQ_SIGNAL = r"(row_dq|agg_dq|query_dq|action_if_failed|DQ_(FLD|STA|REC)_\d+|threshold_exceeded)"
CONDITION_RULES: list[ConditionRule] = [
    ConditionRule(
        r"ImportError.*spark_expectations|No module named ['\"]?spark_expectations|SE_IMPORT_FAILED",  # noqa: E501
        "SE ImportError at runtime",
        "Missing-SE (§8.6)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"SE_RUN_MISSING_FOR_DS",
        "Pipeline task failure after all retries",
        "SE run-evidence gate (§8.6 / Decision 16)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"GOLD_RECON_FAILED_FOR_DS",
        "Row count drop > 5% from baseline (query_dq)",
        "SE stats (§8.3)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"Connection refused.*:8080|Failed to connect.*8080|unity-catalog.*(unreachable|refused)|UCSingleCatalog.*(timeout|refused)|java\.net\.ConnectException|NoSuchCatalogException|Catalog not found",  # noqa: E501
        "UC OSS unreachable after circuit-breaker retries",
        "Transient/infra (§8.1)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"Error code is: -9|OutOfMemoryError|Killed process|exit code 137",
        "Pipeline task failure after all retries",
        "Transient/infra (§8.1) — OOM",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        rf"(?=.*(clinical_allergies|allerg))(?=.*{DQ_SIGNAL})",
        "Allergy DQ failure (any clinical_allergies rule)",
        "SE _error (§8.2)",
        "CRITICAL",
        "PagerDuty p360-critical + Clinical Ops Director",
        "10 min",
    ),
    ConditionRule(
        # SparkExpectationsMiscException is SE's wrapper for ANY internal error (audit-table
        # write, UC outage); only the fail-action exceptions prove a rule verdict.
        r"action_if_failed['\"]?\s*[:=]\s*['\"]?fail|SparkExpectOrFailException|SparkExpectationsErrorThresholdExceedsException|row_dq_error_threshold_exceeded",  # noqa: E501
        "action_if_failed: fail on any rule (row_dq/agg_dq/query_dq)",
        "SE _error or stats (§8.2/§8.3)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"agg_dq.*(breach|exceed|fail)",
        "Agg_dq threshold breach",
        "SE stats (§8.3)",
        "WARNING",
        "Slack #data-alerts-{env}",
        "1 hour",
    ),
    ConditionRule(
        r"SCD2.*mid-batch|mid-batch change",
        "SCD2 mid-batch change detected (query_dq)",
        "SE stats (§8.3)",
        "WARNING",
        "Slack #data-alerts-{env}",
        "4 hours",
    ),
    ConditionRule(
        r"dead[-_]letter|DLQ",
        "Ingest DLQ row count > 0",
        "Ingest DLQ (§8.4)",
        "WARNING",
        "Slack #data-alerts-{env}",
        "1 hour",
    ),
    ConditionRule(
        r"gold.*(overwrite|write).*(fail|error)",
        "Gold table overwrite failure",
        "Transient/infra (§8.1)",
        "CRITICAL",
        "PagerDuty p360-critical",
        "15 min",
    ),
    ConditionRule(
        r"(timeout|timed out|AirflowTaskTimeout)",
        "Pipeline runtime > 45 min",
        "Transient/infra (§8.1)",
        "WARNING",
        "Slack #data-alerts-{env}",
        "1 hour",
    ),
]

FALLBACK_RULE = ConditionRule(
    r".*",
    "Pipeline task failure after all retries",
    "Transient/infra (§8.1)",
    "CRITICAL",
    "PagerDuty p360-critical",
    "15 min",
)


def classify(text: str, task_id: str = "") -> ConditionRule:
    """Return the first LLD §8.5 rule whose marker appears in ``text`` or ``task_id``.

    Explicit mechanism markers win over the task name: ``ingest_allergies`` failing
    on ``java.net.ConnectException`` is a UC outage, not an allergy DQ failure.
    """
    hay = f"{task_id}\n{text or ''}"
    for rule in CONDITION_RULES:
        if re.search(rule.pattern, hay, re.IGNORECASE | re.DOTALL):
            return rule
    return FALLBACK_RULE


def expected_for_condition(condition: str) -> ConditionRule | None:
    for rule in CONDITION_RULES + [FALLBACK_RULE]:
        if rule.condition == condition:
            return rule
    return None


def ds_from_run_id(run_id: str | None) -> str | None:
    if not run_id:
        return None
    m = re.search(r"(\d{4}-\d{2}-\d{2})", run_id)
    return m.group(1) if m else None


def validate_alert(alert: dict[str, Any]) -> list[str]:
    """Return a list of problems (empty when the alert satisfies the contract)."""
    problems: list[str] = []
    for f in REQUIRED_ALERT_FIELDS:
        if not alert.get(f):
            problems.append(f"missing required field: {f}")
    if alert.get("severity") and alert["severity"] not in VALID_SEVERITIES:
        problems.append(f"severity must be one of {VALID_SEVERITIES}, got {alert['severity']!r}")
    if alert.get("source") and alert["source"] not in VALID_SOURCES:
        problems.append(f"source must be one of {VALID_SOURCES}, got {alert['source']!r}")
    if alert.get("source") == "airflow" and not (alert.get("dag_id") and alert.get("task_id")):
        problems.append("airflow-sourced alerts need dag_id and task_id")
    if alert.get("ds") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(alert["ds"])):
        problems.append(f"ds must be YYYY-MM-DD, got {alert['ds']!r}")
    unknown = set(alert) - set(REQUIRED_ALERT_FIELDS) - set(OPTIONAL_ALERT_FIELDS)
    if unknown:
        problems.append(f"unknown fields: {sorted(unknown)}")
    return problems


def make_alert_id(task_id: str, fired_at: str | None = None) -> str:
    ts = fired_at or datetime.now(timezone.utc).isoformat()
    ts = re.sub(r"[^0-9T]", "", ts.split(".")[0].split("+")[0])[:15]
    return f"ALERT-{ts}Z-{task_id}"


# --------------------------------------------------------------------------
# HTTP (GET-only) + Airflow client
# --------------------------------------------------------------------------
class HttpError(Exception):
    def __init__(self, status: int | None, url: str, body: str = ""):
        super().__init__(f"HTTP {status} for {url}: {body[:200]}")
        self.status = status
        self.url = url
        self.body = body


def http_get(
    url: str, headers: dict[str, str] | None = None, timeout: int = HTTP_TIMEOUT
) -> tuple[int, str]:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (local stack)
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise HttpError(None, url, str(exc)) from exc


def http_get_json(url: str, headers: dict[str, str] | None = None) -> Any:
    status, body = http_get(url, headers)
    if status >= 400:
        raise HttpError(status, url, body)
    return json.loads(body) if body else {}


class AirflowClient:
    """Minimal GET-only Airflow 3.x REST client (plus the one POST needed to mint a JWT)."""

    def __init__(
        self, api: str | None = None, user: str | None = None, password: str | None = None
    ):
        self.api = (api or airflow_api()).rstrip("/")
        self.user = user or os.environ.get("AIRFLOW_USER", "admin")
        self.password = password or os.environ.get("AIRFLOW_PASSWORD", "admin")
        self._token: str | None = None

    # The token endpoint is the only non-GET call this plugin ever makes.
    def token(self) -> str:
        if self._token:
            return self._token
        url = airflow_auth_url()
        payload = json.dumps({"username": self.user, "password": self.password}).encode()
        req = urllib.request.Request(
            url, data=payload, method="POST", headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:  # noqa: S310
                status, body = resp.status, resp.read().decode()
        except urllib.error.HTTPError as exc:
            raise HttpError(exc.code, url, exc.read().decode(errors="replace")) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise HttpError(None, url, str(exc)) from exc
        if status not in (200, 201):
            raise HttpError(status, url, body)
        self._token = json.loads(body)["access_token"]
        return self._token

    def _headers(self, accept: str = "application/json") -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token()}", "Accept": accept}

    def get(self, path: str, **params: Any) -> Any:
        url = f"{self.api}{path}"
        if params:
            url += "?" + urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return http_get_json(url, self._headers())

    def dags(self, limit: int = 100) -> list[dict]:
        return self.get("/dags", limit=limit).get("dags", [])

    def dag_runs(self, dag_id: str, state: str | None = "failed", limit: int = 5) -> list[dict]:
        return self.get(
            f"/dags/{dag_id}/dagRuns", state=state, order_by="-end_date", limit=limit
        ).get("dag_runs", [])

    def dag_run(self, dag_id: str, run_id: str) -> dict:
        return self.get(f"/dags/{dag_id}/dagRuns/{urllib.parse.quote(run_id, safe='')}")

    def task_instances(self, dag_id: str, run_id: str, limit: int = 200) -> list[dict]:
        return self.get(
            f"/dags/{dag_id}/dagRuns/{urllib.parse.quote(run_id, safe='')}/taskInstances",
            limit=limit,
        ).get("task_instances", [])

    def task_log(self, dag_id: str, run_id: str, task_id: str, try_number: int) -> str:
        url = (
            f"{self.api}/dags/{dag_id}/dagRuns/{urllib.parse.quote(run_id, safe='')}"
            f"/taskInstances/{task_id}/logs/{try_number}?full_content=true"
        )
        # Airflow 3.2 answers 406 to Accept: text/plain ("Only application/json or
        # application/x-ndjson is supported"); the JSON body is flattened below.
        status, body = http_get(url, self._headers(accept="application/json"))
        if status >= 400:
            raise HttpError(status, url, body)
        return _flatten_log(body)


def _flatten_log(body: str) -> str:
    """Airflow 3 may return plain text or JSON ``{"content": [...]}``; normalise to text."""
    stripped = body.lstrip()
    if not stripped.startswith("{"):
        return body
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return body
    content = data.get("content", body)
    if isinstance(content, str):
        return content
    lines: list[str] = []
    for item in content:
        if isinstance(item, str):
            lines.append(item)
        elif isinstance(item, dict):
            lines.append(item.get("event") or item.get("message") or json.dumps(item))
    return "\n".join(lines)


# --------------------------------------------------------------------------
# Subprocess (read-only commands only; callers pass the argv)
# --------------------------------------------------------------------------
def run_cmd(argv: list[str], timeout: int = 60, cwd: Path | None = None) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, cwd=cwd)  # noqa: S603
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError as exc:
        return 127, "", str(exc)
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s: {' '.join(argv)}"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


def eprint(*args: Any) -> None:
    print(*args, file=sys.stderr)
