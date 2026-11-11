"""Tests for the SRE PreToolUse hook: real mutations are denied, quoted prose is not."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

HOOK = Path(__file__).resolve().parents[3] / "scripts" / "enforce-readonly-queries.py"

spec = importlib.util.spec_from_file_location("sre_hook", HOOK)
hook = importlib.util.module_from_spec(spec)
sys.modules["sre_hook"] = hook
spec.loader.exec_module(hook)


DENIED = [
    "docker compose restart airflow",
    "docker compose -f _infra/docker/docker-compose.yml down",
    "docker pause patient_360-uc",
    "docker compose exec -T airflow rm -rf /opt/airflow/logs",
    "airflow tasks clear patient360_hourly_v1 -t reconciliation_bronze -y",
    'airflow dags trigger patient360_hourly_v1 --conf \'{"ds": "2026-10-14"}\'',
    "curl -X POST http://localhost:8081/api/v2/dags/patient360_hourly_v1/dagRuns -d '{}'",
    "curl --request PATCH http://localhost:8081/api/v2/dags/x",
    "docker compose exec -T spark-thrift-server beeline -u jdbc:hive2://localhost:10000 -e \"DELETE FROM unity.bronze.synthea_patients WHERE ds='2026-10-14'\"",  # noqa: E501
    'beeline -e "RESTORE TABLE unity.gold.patient_summary TO VERSION AS OF 41"',
    'beeline -e "INSERT OVERWRITE unity.bronze.x SELECT * FROM y"',
    "spark-sql -e 'VACUUM unity.bronze.synthea_patients'",
    "git push origin main --force",
    "rm -rf outputs/rca",
]

ALLOWED = [
    "docker compose -f x.yml logs --no-color --tail 500 airflow",
    "docker compose -f x.yml ps --all --format json",
    'docker compose -f x.yml exec -T spark-thrift-server beeline -e "SELECT * FROM unity.bronze.synthea_patients_stats ORDER BY meta_dq_run_datetime DESC LIMIT 5"',  # noqa: E501
    'beeline -e "DESCRIBE HISTORY unity.gold.patient_summary LIMIT 10"',
    'curl -X POST http://localhost:8081/auth/token -d \'{"username":"admin"}\'',
    "curl -s http://localhost:8081/api/v2/dags/x/dagRuns?state=failed",
    "grep -rn 'update' src/",
    "python3 sre-plugin/skills/rca/scripts/collect_evidence.py --alert a.json --offline",
    # Prose that quotes a recovery command inside a heredoc must NOT be blocked.
    "cat > outputs/rca/v1/A/RCA.md <<'EOF'\n### Immediate recovery\n1. Re-run: `airflow dags trigger patient360_hourly_v1 --conf '{\"ds\": \"2026-10-14\"}'`\n2. If needed: `RESTORE TABLE unity.gold.patient_summary TO VERSION AS OF 41`\nEOF",  # noqa: E501
    "python3 - <<'EOF'\nsteps = [\"docker compose restart airflow\", \"DELETE FROM x\"]\nopen('r.md','w').write('\\n'.join(steps))\nEOF",  # noqa: E501
    "python3 -c \"print('airflow dags trigger x')\"",
    "echo 'operators may run: docker compose restart airflow' >> notes.md",
]


@pytest.mark.parametrize("cmd", DENIED)
def test_denied(cmd):
    assert hook.find_violation(cmd) is not None, cmd


@pytest.mark.parametrize("cmd", ALLOWED)
def test_allowed(cmd):
    assert hook.find_violation(cmd) is None, cmd


def test_hook_process_contract():
    payload = json.dumps({"tool_input": {"command": "docker compose restart airflow"}})
    out = subprocess.run([sys.executable, str(HOOK)], input=payload, capture_output=True, text=True)
    assert out.returncode == 0
    decision = json.loads(out.stdout)
    hso = decision["hookSpecificOutput"]
    # Claude Code ignores the decision unless hookEventName is present
    # (verified headless, 2026-10-15).
    assert hso["hookEventName"] == "PreToolUse"
    assert hso["permissionDecision"] == "deny"
    assert "Immediate recovery" in hso["permissionDecisionReason"]
    assert "Immediate recovery" in decision["systemMessage"]
    ok = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({"tool_input": {"command": "ls"}}),
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0 and ok.stdout == ""


def test_hook_is_executable_with_shebang():
    """hooks.json invokes the script directly; without +x Claude Code silently skips the hook."""
    import os

    assert os.access(HOOK, os.X_OK), f"{HOOK} must be executable (chmod +x)"
    assert HOOK.read_text().startswith("#!/usr/bin/env python3")
