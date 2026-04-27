"""Verify the per-task entry-wrapper Jinja template renders correctly.

The chapter-5 developer-plugin auto-generates `airflow/jobs/run_<task_type>.py`
shims from `inputs/code/v1/scripts/run_layer_entrypoint.py.j2`, one per
distinct task type listed in LLD §4.2. This test exercises the template
with a synthetic LLD §4.2 (three task types) and asserts each rendered
wrapper:
- imports the right runner module
- argv-parses the LLD §5 task signature
- has a callable `main(argv)` entry point that delegates to the runner
- never emits `application="-m module.path"` style invocation

Why: spokane spent the first end-to-end run debugging
`PermissionError: '-m'` because the original wrapper used invalid
`application="-m"` semantics. Auto-generation + this regression test
prevents the bug from coming back.
"""
# ruff: noqa: E501

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

CHAPTER5_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = CHAPTER5_ROOT / "inputs/code/v1/scripts/run_layer_entrypoint.py.j2"


def _render(task_type: str, runner_module: str, entry: str, argv_spec: list[dict]) -> str:
    jinja2 = pytest.importorskip("jinja2")
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_PATH.parent)),
        keep_trailing_newline=True,
    )
    return env.get_template(TEMPLATE_PATH.name).render(
        project="patient_360",
        task_type=task_type,
        runner_module=runner_module,
        entry_function=entry,
        argv_spec=argv_spec,
    )


SYNTHETIC_LLD_TASK_TYPES = [
    {
        "task_type": "bronze_ingestion",
        "runner_module": "patient_360.bronze.ingestion_runner",
        "entry": "main",
        "argv_spec": [
            {"name": "--config-path", "required": True, "help": "Per-table YAML config path"},
            {"name": "--ds", "required": True, "help": "Logical date YYYY-MM-DD"},
        ],
    },
    {
        "task_type": "bronze_recon",
        "runner_module": "patient_360.bronze.reconciliation",
        "entry": "main",
        "argv_spec": [
            {"name": "--ds", "required": True, "help": "Logical date YYYY-MM-DD"},
            {
                "name": "--configs-dir",
                "required": False,
                "help": "Per-table YAML configs directory",
            },
        ],
    },
    {
        "task_type": "silver_dim",
        "runner_module": "patient_360.silver.dim_runner",
        "entry": "run",
        "argv_spec": [
            {"name": "--table", "required": True, "help": "Silver dim table name"},
            {"name": "--ds", "required": True, "help": "Logical date YYYY-MM-DD"},
        ],
    },
]


class TestRunLayerEntrypointTemplate:
    def test_template_exists(self):
        assert TEMPLATE_PATH.is_file(), (
            f"Jinja template missing at {TEMPLATE_PATH.relative_to(CHAPTER5_ROOT)}; "
            "create-dag Phase 3b cannot generate wrappers without it."
        )

    @pytest.mark.parametrize("spec", SYNTHETIC_LLD_TASK_TYPES, ids=lambda s: s["task_type"])
    def test_renders_per_task_type(self, spec):
        rendered = _render(
            spec["task_type"], spec["runner_module"], spec["entry"], spec["argv_spec"]
        )
        # Imports the right runner module via importlib (survives runner refactors).
        assert f'importlib.import_module("{spec["runner_module"]}")' in rendered
        # Entry function name resolves correctly.
        assert f'"{spec["entry"]}"' in rendered
        # Every argv arg ends up as a p.add_argument(...) call.
        for arg in spec["argv_spec"]:
            assert f'"{arg["name"]}"' in rendered, f"argv {arg['name']} missing"
            assert arg["help"] in rendered, f"help text for {arg['name']} missing"
        # Has a real `main(argv)` entry function — not `-m module.path` style.
        assert "def main(argv:" in rendered or "def main(argv " in rendered
        # Never the bug we're guarding against.
        assert "-m module.path" not in rendered
        assert 'application="-m"' not in rendered

    def test_rendered_wrapper_is_executable_python(self, tmp_path):
        spec = SYNTHETIC_LLD_TASK_TYPES[0]
        rendered = _render(
            spec["task_type"], spec["runner_module"], spec["entry"], spec["argv_spec"]
        )
        wrapper = tmp_path / f"run_{spec['task_type']}.py"
        wrapper.write_text(rendered, encoding="utf-8")
        # Compile-only — confirms the rendered shim is syntactically valid.
        compiled = importlib.util.spec_from_file_location("wrapper_under_test", wrapper)
        assert compiled is not None
        # Loading would import the runner module which doesn't exist in this
        # test env — that's fine, syntax-validity is the gate here.
        compile(rendered, str(wrapper), mode="exec")
