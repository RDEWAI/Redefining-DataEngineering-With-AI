"""Unit tests for :mod:`patient_360.utils.se_runner` (STORY-01-010 /
STORY-02-010, v2.9).

Covers the LLD §2.3 item 3 (v1.20) / §5.4 contract:

* ``run_dq`` exposes the agreed signature.
* ``--env`` is mapped to SE ``dq_env`` per the LLD table
  (DEV→DEV, STAGING→QA, PROD→PROD); unknown envs raise ``KeyError``.
* ``run_dq`` calls ``SparkExpectations.with_expectations`` with BOTH the
  error and stats tables ENABLED — the UC 0.5.0 managed-audit-table contract
  (LLD §13 Decision 12 corrected 2026-06-20).
* The SE stats/error tables are per-table MANAGED UC tables addressed by a
  3-part FQN derived from ``target_table`` — NOT path-based writers.
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


def _write_rule_stub(rules_dir: Path, table: str, table_name: str | None = None) -> Path:
    """Write a minimal YAML rule file so the existence check passes.

    ``table_name`` defaults to the FQN ``unity.bronze.<table>`` so the
    derived SE audit tables are well-formed 3-part names.
    """
    rules_dir.mkdir(parents=True, exist_ok=True)
    tn = table_name or f"unity.bronze.{table}"
    p = rules_dir / f"{table}.yml"
    p.write_text(
        "product_id: patient-360\n"
        "dq_env:\n"
        "  DEV:\n"
        f"    table_name: {tn}\n"
        "  QA:\n"
        f"    table_name: {tn}\n"
        "rules: []\n"
    )
    return p


# ---------------------------------------------------------------------------
# FQN qualification (LLD §2.3 item 3 v1.20 / §13 Decision 12 corrected)
# ---------------------------------------------------------------------------
def test_qualify_target_table_qualifies_bare_name(monkeypatch):
    """A BARE table_name is qualified to ``unity.bronze.<table>`` so SE's
    derived ``<target>_error`` / ``_stats`` are well-formed 3-part FQNs."""
    monkeypatch.delenv(se_runner.UC_CATALOG_ENV, raising=False)
    monkeypatch.delenv(se_runner.UC_BRONZE_SCHEMA_ENV, raising=False)
    assert se_runner._qualify_target_table("synthea_patients") == "unity.bronze.synthea_patients"


def test_qualify_target_table_passthrough_for_fqn():
    """An already-qualified FQN is returned unchanged."""
    assert (
        se_runner._qualify_target_table("unity.bronze.synthea_patients")
        == "unity.bronze.synthea_patients"
    )


def test_qualify_target_table_honours_env_overrides(monkeypatch):
    monkeypatch.setenv(se_runner.UC_CATALOG_ENV, "mycat")
    monkeypatch.setenv(se_runner.UC_BRONZE_SCHEMA_ENV, "myschema")
    assert se_runner._qualify_target_table("t") == "mycat.myschema.t"


def test_run_dq_enables_both_managed_audit_tables(tmp_path):
    """AC2 / §13 Decision 12 (corrected): run_dq calls with_expectations with
    BOTH the error AND stats tables ENABLED (UC 0.5.0 managed-audit-table
    contract — the prior ``se.enable.error.table=False`` workaround is gone)."""
    _write_rule_stub(tmp_path, "patients")

    df = MagicMock()
    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda func: func  # decorator factory
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se) as se_cls,
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        run_dq(
            df,
            table="patients",
            env="STAGING",
            dq_rules_dir=tmp_path,
            action_if_failed="fail",
            quarantine_path="/tmp/q/patients",
        )

    assert se_cls.called, "SparkExpectations should be constructed"
    args, kwargs = fake_se.with_expectations.call_args
    user_conf = kwargs["user_conf"]
    # UC 0.5.0 managed audit tables — both ENABLED.
    assert user_conf["se.enable.error.table"] is True
    assert user_conf["se.enable.stats.table"] is True

    # Loader was invoked with the mapped dq_env (STAGING → QA).
    loader_args, loader_kwargs = fake_loader.load_rules.call_args
    assert loader_kwargs["options"]["dq_env"] == "QA"


def test_run_dq_writers_are_managed_no_path_option(tmp_path):
    """§13 Decision 12 (corrected): both the SE stats and error writers are
    MANAGED — ``WrappedDataFrameWriter().mode("append").format("delta")`` with
    NO ``.option("path", ...)``. ``stats_table`` handed to SparkExpectations
    is the 3-part FQN ``<target>_stats``, not a ``delta.`<path>``` identifier
    and not a filesystem path."""
    _write_rule_stub(tmp_path, "patients")

    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda func: func
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se) as se_cls,
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        run_dq(
            MagicMock(),
            table="patients",
            env="DEV",
            dq_rules_dir=tmp_path,
        )

    _se_args, se_kwargs = se_cls.call_args
    stats_table = se_kwargs["stats_table"]
    # 3-part FQN ending in `_stats`, NOT a path-table identifier or path.
    assert stats_table == "unity.bronze.patients_stats"
    assert "delta.`" not in stats_table
    assert "/" not in stats_table

    # Neither writer carries a `path` option → SE takes the managed
    # `saveAsTable` branch.
    stats_writer_cfg = se_kwargs["stats_table_writer"].build()
    error_writer_cfg = se_kwargs["target_and_error_table_writer"].build()
    assert "path" not in stats_writer_cfg.get("options", {})
    assert "path" not in error_writer_cfg.get("options", {})
    assert stats_writer_cfg["mode"] == "append"
    assert stats_writer_cfg["format"] == "delta"


def test_run_dq_target_table_is_fqn_from_yaml(tmp_path):
    """STORY-02-010 AC1/AC2 + §2.3 item 3: product_id comes from the YAML
    top-level field; target_table is the dq_env.<ENV>.table_name FQN passed
    straight through to with_expectations (well-formed 3-part name)."""
    _write_rule_stub(tmp_path, "patients", table_name="unity.bronze.synthea_patients")

    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda func: func
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se) as se_cls,
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        run_dq(MagicMock(), table="patients", env="DEV", dq_rules_dir=tmp_path)

    _se_args, se_kwargs = se_cls.call_args
    assert se_kwargs["product_id"] == "patient-360"
    assert se_kwargs["product_id"] != "patients"
    # stats_table is the FQN-derived `<target>_stats`.
    assert se_kwargs["stats_table"] == "unity.bronze.synthea_patients_stats"
    # target_table handed to with_expectations is the FQN.
    we_args, we_kwargs = fake_se.with_expectations.call_args
    assert we_kwargs["target_table"] == "unity.bronze.synthea_patients"


def test_run_dq_qualifies_bare_table_name_from_yaml(tmp_path, monkeypatch):
    """A BARE dq_env table_name in the YAML is qualified to
    ``unity.bronze.<name>`` before being handed to SE, so the derived audit
    tables are valid 3-part FQNs (the empty-namespace crash guard)."""
    monkeypatch.delenv(se_runner.UC_CATALOG_ENV, raising=False)
    monkeypatch.delenv(se_runner.UC_BRONZE_SCHEMA_ENV, raising=False)
    _write_rule_stub(tmp_path, "patients", table_name="synthea_patients")

    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda func: func
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se) as se_cls,
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        run_dq(MagicMock(), table="patients", env="DEV", dq_rules_dir=tmp_path)

    we_args, we_kwargs = fake_se.with_expectations.call_args
    assert we_kwargs["target_table"] == "unity.bronze.synthea_patients"
    _se_args, se_kwargs = se_cls.call_args
    assert se_kwargs["stats_table"] == "unity.bronze.synthea_patients_stats"


def test_run_dq_returns_validated_df(tmp_path):
    """Sanity: run_dq returns the validated frame projected to input cols.

    STORY-02-010 AC8: run_dq returns ``validated.select(*input_cols)`` so SE's
    appended run-tracking columns are dropped.
    """
    _write_rule_stub(tmp_path, "encounters")

    input_df = MagicMock(name="input_df")
    input_df.columns = ["patient_id", "ds"]
    validated = MagicMock(name="validated_df")
    projected = MagicMock(name="projected_df")
    validated.select.return_value = projected

    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda _func: lambda: validated
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se),
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        out = run_dq(
            input_df,
            table="encounters",
            env="DEV",
            dq_rules_dir=tmp_path,
            action_if_failed="drop",
        )

    validated.select.assert_called_once_with("patient_id", "ds")
    assert out is projected


def test_run_dq_is_column_stable(tmp_path):
    """STORY-02-010 AC8: run_dq captures input columns BEFORE
    with_expectations and projects the validated frame back to them, dropping
    SE's appended run-tracking columns so output schema equals input schema."""
    _write_rule_stub(tmp_path, "patients")

    input_df = MagicMock(name="input_df")
    input_df.columns = ["patient_id", "first_name", "ds"]
    validated = MagicMock(name="validated_df")
    validated.columns = [
        "patient_id",
        "first_name",
        "ds",
        "meta_dq_run_id",
        "meta_dq_run_datetime",
    ]
    validated.select.return_value = MagicMock(name="projected_df")

    fake_se = MagicMock()
    fake_se.with_expectations.return_value = lambda _func: lambda: validated
    fake_loader = MagicMock()
    fake_loader.load_rules.return_value = MagicMock(name="rules_df")

    with (
        patch.object(se_runner, "SparkExpectations", return_value=fake_se),
        patch.object(
            se_runner,
            "SparkExpectationsYamlRuleLoaderImpl",
            return_value=fake_loader,
        ),
    ):
        run_dq(input_df, table="patients", env="DEV", dq_rules_dir=tmp_path)

    validated.select.assert_called_once_with("patient_id", "first_name", "ds")
