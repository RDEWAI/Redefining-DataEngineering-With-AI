# ruff: noqa: E501 -- GOOD_REPORT is a markdown fixture with wide table rows
"""Unit tests for check_report.py: a good report passes, each CRITICAL rule fires on a mutation."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

import check_report as cr  # noqa: E402

GOOD_REPORT = """# RCA: ALERT-1-reconciliation_bronze

## 1. Alert Summary

| Field | Value |
|---|---|
| Condition (LLD §8.5) | Pipeline task failure after all retries |
| Severity / channel | CRITICAL / PagerDuty p360-critical |

## 2. Timeline

| Time | Event | Evidence |
|---|---|---|
| 15:00 | run start | `evidence/airflow_dagrun.json` |

## 3. Evidence Collected

| Surface | Status | File |
|---|---|---|
| airflow_task_log | ok | airflow_task_log_try3.log |
| se_stats | ok | se_stats.json |
| marquez_runs | unavailable | no jobs |
| docker_logs_marquez | unavailable | not running |

## 4. Hypotheses

| # | Hypothesis | Failure class | Evidence that would confirm | Verdict | Evidence cited |
|---|---|---|---|---|---|
| H1 | SE never ran for bronze tables | SE gate | no recent stats rows | CONFIRMED | `evidence/se_stats.json` |
| H2 | UC unreachable | infra | 5xx in uc log | REFUTED | `evidence/docker_logs_unity-catalog.log` line 12 |
| H3 | OOM | infra | -9 in task log | OPEN | |

## 5. Root Cause

**CONFIRMED** — reconciliation_bronze raised SE_RUN_MISSING_FOR_DS because se_runner was skipped.

Mechanism: assert_se_evidence counts stats rows and found 0.

## 6. Blast Radius

- Downstream tasks affected: transform_patients_silver

## 7. Remediation

### Immediate recovery (operator)
1. Re-run the task.

### Permanent fix (owner: ingestion)
Set `dq_enabled: true` in airflow/configs/patients.yml.

```
/developer-plugin:update-ingestion patients
```

### Prevention
- Add a DAG unit test.

## 8. Severity & Escalation

| | Fired | LLD §8.5 expects |
|---|---|---|
| Severity | CRITICAL | CRITICAL |
| Channel | PagerDuty p360-critical | PagerDuty p360-critical |

## 9. References

- LLD §8.5
"""

ALERT = {
    "alert_id": "ALERT-1-reconciliation_bronze",
    "ds": "2026-10-14",
    "condition": "Pipeline task failure after all retries",
    "severity": "CRITICAL",
}
MANIFEST = {
    "surfaces": {
        "airflow_task_log": {"status": "ok"},
        "se_stats": {"status": "ok"},
        "marquez_runs": {"status": "unavailable"},
        "docker_logs_marquez": {"status": "unavailable"},
    }
}


@pytest.fixture
def report_dir(tmp_path: Path) -> Path:
    d = tmp_path / "ALERT-1-reconciliation_bronze"
    (d / "evidence").mkdir(parents=True)
    (d / "alert.json").write_text(json.dumps(ALERT))
    (d / "evidence" / "manifest.json").write_text(json.dumps(MANIFEST))
    for f in ("se_stats.json", "docker_logs_unity-catalog.log", "airflow_dagrun.json"):
        (d / "evidence" / f).write_text("{}")
    return d


@pytest.fixture
def ws(tmp_path: Path) -> Path:
    root = tmp_path / "ws"
    (root / "developer-plugin" / "skills" / "update-ingestion").mkdir(parents=True)
    return root


def _write(report_dir: Path, text: str) -> Path:
    p = report_dir / "RCA-2026-10-14-ALERT-1-reconciliation_bronze.md"
    p.write_text(text)
    return p


def test_good_report_passes(report_dir, ws):
    f = cr.check(_write(report_dir, GOOD_REPORT), ws)
    assert f.critical == [], f.critical
    assert f.warning == [], f.warning
    assert any("marquez" in i for i in f.info)
    assert "Result: PASS" in f.render()


def test_missing_section_is_critical(report_dir, ws):
    f = cr.check(_write(report_dir, GOOD_REPORT.replace("## 6. Blast Radius", "## 6. Impact")), ws)
    assert any("Blast Radius" in c for c in f.critical) or any("section 6" in w for w in f.warning)
    f2 = cr.check(
        _write(report_dir, GOOD_REPORT.replace("## 9. References\n\n- LLD §8.5\n", "")), ws
    )
    assert any("## 9. References" in c for c in f2.critical)


def test_indeterminate_without_missing_evidence_is_critical(report_dir, ws):
    text = GOOD_REPORT.replace(
        "**CONFIRMED** — reconciliation_bronze", "**INDETERMINATE** — reconciliation_bronze"
    )
    f = cr.check(_write(report_dir, text), ws)
    assert any("INDETERMINATE" in c for c in f.critical)
    ok = text.replace(
        "Mechanism:", "Missing evidence: se_stats for every bronze table.\nMechanism:"
    )
    f2 = cr.check(_write(report_dir, ok), ws)
    assert not any("INDETERMINATE" in c for c in f2.critical)


def test_confirmed_hypothesis_without_evidence_is_critical(report_dir, ws):
    text = GOOD_REPORT.replace("| CONFIRMED | `evidence/se_stats.json` |", "| CONFIRMED | |")
    f = cr.check(_write(report_dir, text), ws)
    assert any("cites no evidence" in c for c in f.critical)


def test_cited_evidence_must_exist(report_dir, ws):
    text = GOOD_REPORT.replace("`evidence/se_stats.json`", "`evidence/se_stats_v2.json`")
    f = cr.check(_write(report_dir, text), ws)
    assert any("does not exist" in c for c in f.critical)


def test_remediation_needs_valid_owner(report_dir, ws):
    text = GOOD_REPORT.replace(
        "/developer-plugin:update-ingestion patients", "/developer-plugin:update-everything"
    )
    f = cr.check(_write(report_dir, text), ws)
    assert any("no such skill" in c for c in f.critical)
    none = GOOD_REPORT.replace(
        "```\n/developer-plugin:update-ingestion patients\n```", "nothing to do"
    )
    f2 = cr.check(_write(report_dir, none), ws)
    assert any("names no owner skill" in c for c in f2.critical)
    ok = GOOD_REPORT.replace(
        "```\n/developer-plugin:update-ingestion patients\n```", "No code change required."
    )
    f3 = cr.check(_write(report_dir, ok), ws)
    assert f3.critical == []


def test_ds_filtered_se_evidence_is_critical(report_dir, ws):
    # A claim in §4 that filters by ds is CRITICAL ...
    text = GOOD_REPORT.replace(
        "| CONFIRMED | `evidence/se_stats.json` |",
        "| CONFIRMED | `evidence/se_stats.json` WHERE meta_dq_run_date = '2026-10-14' |",
    )
    f = cr.check(_write(report_dir, text), ws)
    assert any("meta_dq_run_date = ds" in c for c in f.critical)
    # ... but explaining the gate's own query in §5 prose is allowed.
    text2 = GOOD_REPORT.replace(
        "Mechanism:",
        "Mechanism: the gate runs SELECT count(*) WHERE meta_dq_run_date = '2026-10-14' and",
    )
    f2 = cr.check(_write(report_dir, text2), ws)
    assert not any("meta_dq_run_date = ds" in c for c in f2.critical)
    # An "Evidence:" line in §5 is a claim again.
    text3 = GOOD_REPORT.replace(
        "Mechanism:", "Evidence: se_stats.json WHERE meta_dq_run_date = '2026-10-14'\nMechanism:"
    )
    f3 = cr.check(_write(report_dir, text3), ws)
    assert any("meta_dq_run_date = ds" in c for c in f3.critical)


def test_hedging_and_severity_mismatch_are_warnings(report_dir, ws):
    text = GOOD_REPORT.replace(
        "because se_runner was skipped", "probably because se_runner was skipped"
    )
    text = text.replace("| Severity | CRITICAL | CRITICAL |", "| Severity | WARNING | WARNING |")
    text = text.replace(
        "| Severity / channel | CRITICAL / PagerDuty p360-critical |",
        "| Severity / channel | WARNING / Slack |",
    )
    text = text.replace(
        "| Channel | PagerDuty p360-critical | PagerDuty p360-critical |",
        "| Channel | Slack | Slack |",
    )
    f = cr.check(_write(report_dir, text), ws)
    assert any("hedging" in w for w in f.warning)
    assert any("severity CRITICAL" in w for w in f.warning)
    assert any("channel" in w for w in f.warning)
    assert f.critical == []


def test_unacknowledged_unavailable_surface_is_warning(report_dir, ws):
    manifest = {
        "surfaces": {
            **MANIFEST["surfaces"],
            "uc_health": {"status": "unavailable", "reason": "refused"},
        }
    }
    (report_dir / "evidence" / "manifest.json").write_text(json.dumps(manifest))
    f = cr.check(_write(report_dir, GOOD_REPORT), ws)
    assert any("uc_health" in w for w in f.warning)


def test_cli_exit_codes(report_dir, ws, capsys):
    p = _write(report_dir, GOOD_REPORT)
    assert cr.main([str(p), "--workspace-root", str(ws)]) == 0
    assert "Result: PASS" in capsys.readouterr().out
    bad = _write(
        report_dir,
        GOOD_REPORT.replace("| CONFIRMED | `evidence/se_stats.json` |", "| CONFIRMED | |"),
    )
    assert cr.main([str(bad), "--workspace-root", str(ws)]) == 1
