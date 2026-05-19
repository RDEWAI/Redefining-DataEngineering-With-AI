"""Unit tests for :mod:`patient_360.utils.se_runner` (STORY-01-010).

Covers the LLD §2.3 / §5.4 contract:

* ``run_dq`` exposes the agreed signature.
* ``--env`` is mapped to SE ``dq_env`` per the LLD table
  (DEV→DEV, STAGING→QA, PROD→PROD); unknown envs raise ``KeyError``.
* ``run_dq`` calls ``SparkExpectations.with_expectations`` with both the
  error and stats tables enabled — i.e. the fail-closed flags from
  LLD §8.2 / §8.3 are not negotiable.
* ``_resolve_dq_rules_dir`` honours the explicit arg → env var → default
  fallback chain (LLD §2.3).

The tests stub Spark Expectations so they never need an actual Spark
session — they exercise the wiring contract, not the Spark runtime.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from patient_360.utils import se_runner
from patient_360.utils.se_runner import _DQ_ENV_MAP, run_dq


def test_run_dq_signature_matches_lld_2_3():
    """The signature MUST expose the parameters named in LLD §2.3."""
    sig = inspect.signature(run_dq)
    params = set(sig.parameters)
    # The story AC1 enumerates df, table, env, action_if_failed,
    # dq_rules_dir. quarantine_path is an LLD §8.2 addition.
    required = {"df", "table", "env", "action_if_failed", "dq_rules_dir"}
    missing = required - params
    assert not missing, f"run_dq is missing required params: {missing}"


@pytest.mark.parametrize(
    "runtime_env,expected_dq_env",
    [("DEV", "DEV"), ("STAGING", "QA"), ("PROD", "PROD")],
)
def test_dq_env_mapping_matches_lld(runtime_env, expected_dq_env):
    """LLD §2.3 / §5.4 dq_env table is the single source of truth."""
    assert _DQ_ENV_MAP[runtime_env] == expected_dq_env


def test_dq_env_unknown_env_raises():
    """Unknown env → KeyError; fail-closed before SE is even constructed."""
    df = MagicMock()
    with pytest.raises(KeyError):
        run_dq(df, table="patients", env="QA", dq_rules_dir="/tmp/rules")


def test_resolve_dq_rules_dir_explicit_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("DQ_RULES_DIR", str(tmp_path / "env"))
    explicit = tmp_path / "explicit"
    assert se_runner._resolve_dq_rules_dir(explicit) == explicit


def test_resolve_dq_rules_dir_env_var(monkeypatch, tmp_path):
    monkeypatch.setenv("DQ_RULES_DIR", str(tmp_path))
    assert se_runner._resolve_dq_rules_dir(None) == tmp_path


def test_resolve_dq_rules_dir_default(monkeypatch):
    monkeypatch.delenv("DQ_RULES_DIR", raising=False)
    assert se_runner._resolve_dq_rules_dir(None) == Path("/opt/dq_rules")


def test_missing_rules_file_raises(tmp_path):
    df = MagicMock()
    with pytest.raises(FileNotFoundError):
        run_dq(
            df,
            table="does_not_exist",
            env="DEV",
            dq_rules_dir=tmp_path,
        )


def _write_rule_stub(rules_dir: Path, table: str) -> Path:
    """Write a minimal YAML rule file so the existence check passes."""
    rules_dir.mkdir(parents=True, exist_ok=True)
    p = rules_dir / f"{table}.yml"
    p.write_text(
        "product_id: patient_360\n"
        "dq_env: DEV\n"
        "rules: []\n"
    )
    return p


def test_run_dq_invokes_with_expectations_with_error_and_stats_flags(tmp_path):
    """AC2: run_dq calls with_expectations with both SE tables enabled."""
    _write_rule_stub(tmp_path, "patients")

    df = MagicMock()
    # Patch SE wiring so no real Spark is needed.
    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda x: x  # decorator factory
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se) as se_cls,
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
        patch.object(se_runner, "_ensure_stats_table"),
    ):
        run_dq(
            df,
            table="patients",
            env="STAGING",
            dq_rules_dir=tmp_path,
            action_if_failed="fail",
            quarantine_path="/tmp/q/patients",
        )

    # SparkExpectations was constructed.
    assert se_cls.called, "SparkExpectations should be constructed"
    # with_expectations was called with user_conf carrying both flags.
    args, kwargs = fake_se.with_expectations.call_args
    user_conf = kwargs["user_conf"]
    assert user_conf["se.enable.error.table"] is True
    assert user_conf["se.enable.stats.table"] is True

    # Loader was invoked with the mapped dq_env (STAGING → QA).
    loader_args, loader_kwargs = fake_loader.load_rules.call_args
    assert loader_kwargs["options"]["dq_env"] == "QA"


def test_run_dq_returns_validated_df(tmp_path):
    """Sanity: the validated frame is the one with_expectations produced."""
    _write_rule_stub(tmp_path, "encounters")

    sentinel = MagicMock(name="validated_df")
    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda _df: sentinel
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se),
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
        patch.object(se_runner, "_ensure_stats_table"),
    ):
        out = run_dq(
            MagicMock(),
            table="encounters",
            env="DEV",
            dq_rules_dir=tmp_path,
            action_if_failed="drop",
        )
    assert out is sentinel
