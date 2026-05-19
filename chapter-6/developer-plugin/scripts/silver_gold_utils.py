"""Shared helpers for validate_silver.py and validate_gold.py.

These utilities parse the upstream LLD/DMS markdown and provide AST walkers
used by the per-table/per-builder rule checks.

Intentionally dependency-free beyond stdlib + pyyaml; runs anywhere uv sync
has been done.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Findings model
# ---------------------------------------------------------------------------


@dataclass
class Findings:
    critical: list[str] = field(default_factory=list)
    warning: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def critical_count(self) -> int:
        return len(self.critical)

    def add(self, level: str, rule: str, msg: str) -> None:
        line = f"[{rule}] {msg}"
        if level == "CRITICAL":
            self.critical.append(line)
        elif level == "WARNING":
            self.warning.append(line)
        else:
            self.info.append(line)

    def render(self, project_label: str = "") -> str:
        lines = [f"Validation report{(' — ' + project_label) if project_label else ''}", "=" * 60]
        lines.append(f"\nCRITICAL: {len(self.critical)}")
        for item in self.critical:
            lines.append(f"  {item}")
        lines.append(f"\nWARNING: {len(self.warning)}")
        for item in self.warning:
            lines.append(f"  {item}")
        lines.append(f"\nINFO: {len(self.info)}")
        for item in self.info:
            lines.append(f"  {item}")
        lines.append("")
        lines.append(f"Result: {'FAIL' if self.critical else 'PASS'}")
        return "\n".join(lines)

    def to_json(self) -> dict:
        return {
            "critical": self.critical,
            "warning": self.warning,
            "info": self.info,
            "result": "FAIL" if self.critical else "PASS",
        }


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def latest_version_dir(root: Path, artifact: str) -> Path | None:
    """Return ``root/outputs/<artifact>/v<N>/`` with the highest N, or None."""
    base = root / "outputs" / artifact
    if not base.is_dir():
        return None
    versions = sorted((p for p in base.glob("v*") if p.is_dir()), key=lambda p: p.name)
    return versions[-1] if versions else None


def latest_artifact_file(version_dir: Path, prefix: str, suffix: str = ".md") -> Path | None:
    """Return the most-recent ``<prefix>-*<suffix>`` file under version_dir, excluding .bak."""
    candidates = [
        p
        for p in version_dir.glob(f"{prefix}-*{suffix}")
        if not p.name.endswith(".bak")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


# ---------------------------------------------------------------------------
# LLD / DMS markdown parsers
# ---------------------------------------------------------------------------


def extract_metadata_status(md_path: Path) -> str | None:
    """Return the ``Status`` cell in the metadata table at the top of the file."""
    text = md_path.read_text(encoding="utf-8")
    m = re.search(r"\|\s*\*\*Status\*\*\s*\|\s*([^|]+?)\s*\|", text)
    return m.group(1).strip() if m else None


def extract_lld_silver_tasks(lld_path: Path) -> list[dict]:
    """Parse the ``### 5.2 Silver Tasks`` table into a list of dicts.

    Returns one dict per Silver task row with keys: ``task_id``, ``module``,
    ``contract``, ``dq_rules``, ``bronze_input``, ``silver_output``,
    ``transform_ref``, ``dq_check``.
    """
    return _extract_lld_layer_table(lld_path, heading="### 5.2 Silver Tasks")


def extract_lld_gold_tasks(lld_path: Path) -> list[dict]:
    """Parse the ``### 5.3 Gold Tasks`` table into a list of dicts."""
    return _extract_lld_layer_table(lld_path, heading="### 5.3 Gold Tasks")


def _extract_lld_layer_table(lld_path: Path, heading: str) -> list[dict]:
    text = lld_path.read_text(encoding="utf-8")
    idx = text.find(heading)
    if idx == -1:
        return []
    # Bound at the next section of equal or higher level — `\n### ` or `\n## `
    after = idx + len(heading)
    cand_ends = [text.find(marker, after) for marker in ("\n### ", "\n## ")]
    cand_ends = [c for c in cand_ends if c != -1]
    end = min(cand_ends) if cand_ends else len(text)
    section = text[idx:end]
    # Grab the markdown table — the row starting with "| Task ID"
    table_rows = []
    for line in section.splitlines():
        if line.startswith("|") and not line.startswith("|---") and "| Task ID" not in line:
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 5:
                table_rows.append(cells)
    results: list[dict] = []
    for row in table_rows:
        # Defensive: pad to 10 cells
        row = row + [""] * (10 - len(row))
        task_id = row[0].strip("`")
        module_path = row[2]
        contract = row[3]
        dq_rules = row[4]
        # Module path -> bare table name (e.g. transform_patients.py -> patients)
        m = re.search(r"transform_(\w+)\.py|build_(\w+)\.py", module_path)
        bare_table = (m.group(1) or m.group(2)) if m else ""
        results.append(
            {
                "task_id": task_id,
                "module_path": module_path,
                "module_table": bare_table,
                "contract_path": contract,
                "dq_rules_path": dq_rules,
                "inputs": row[6],
                "outputs": row[7],
                "transform_ref": row[8] if len(row) > 8 else "",
                "dq_check": row[9] if len(row) > 9 else "",
            }
        )
    return results


def extract_dms_columns(dms_path: Path, table: str) -> list[str]:
    """Return the column list for a given silver/gold table from DMS §3/§4.

    Looks for a heading containing the table name and parses the subsequent
    markdown column table. Returns column names only; types are not extracted
    here (the contract YAML carries them).
    """
    text = dms_path.read_text(encoding="utf-8")
    # Find heading mentioning the table
    heading_re = re.compile(rf"^#{{2,4}}.*\b{re.escape(table)}\b.*$", re.MULTILINE)
    m = heading_re.search(text)
    if not m:
        return []
    section_start = m.end()
    # Bound at next ## or ### heading
    next_heading = re.search(r"^#{2,4} ", text[section_start:], re.MULTILINE)
    section = text[section_start : section_start + next_heading.start() if next_heading else len(text)]
    cols: list[str] = []
    for line in section.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            # First column is the column name; skip header row
            if cells and cells[0].lower() not in {"column", "name", "field"} and cells[0]:
                cols.append(cells[0])
    return cols


def extract_dms_hash_columns(dms_path: Path, table: str) -> list[str]:
    """Return the SCD2 hash column list for a dim from DMS §6.

    Looks for ``§6`` SCD2 strategy section and a sub-block naming the table.
    """
    text = dms_path.read_text(encoding="utf-8")
    six = re.search(r"^##\s+6\.\s+SCD\s+Strategy", text, re.MULTILINE | re.IGNORECASE)
    if not six:
        return []
    section = text[six.end():]
    next_top = re.search(r"^##\s+\d", section, re.MULTILINE)
    if next_top:
        section = section[: next_top.start()]
    # Find the sub-block for this table
    sub_re = re.compile(rf"^#{{3,4}}.*\b{re.escape(table)}\b.*$", re.MULTILINE | re.IGNORECASE)
    sub = sub_re.search(section)
    if not sub:
        return []
    sub_section = section[sub.end():]
    next_sub = re.search(r"^#{3,4} ", sub_section, re.MULTILINE)
    if next_sub:
        sub_section = sub_section[: next_sub.start()]
    # Try to find a bullet "Hash columns:" line or a "hash_columns:" yaml-ish line
    hc = re.search(r"[Hh]ash\s+columns?\s*[:\-]\s*(.+)", sub_section)
    if not hc:
        return []
    payload = hc.group(1).strip()
    # Strip backticks, brackets, quotes; split on comma/space
    payload = re.sub(r"[`\[\]\"']", "", payload)
    return [c.strip() for c in re.split(r"[,\s]+", payload) if c.strip()]


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def parse_python(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, OSError):
        return None


def imports_name(tree: ast.AST, dotted: str) -> bool:
    """True if the AST imports the dotted name (e.g. 'patient_360.utils.scd2.apply_scd2')."""
    parts = dotted.split(".")
    target_module = ".".join(parts[:-1])
    target_name = parts[-1]
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module == target_module:
                for alias in node.names:
                    if alias.name == target_name:
                        return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == dotted:
                    return True
    return False


def find_calls(tree: ast.AST, func_name: str) -> list[ast.Call]:
    """Return every ``ast.Call`` whose direct callable is ``Name(func_name)``
    or ``Attribute(attr=func_name)``."""
    results: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == func_name:
            results.append(node)
        elif isinstance(fn, ast.Attribute) and fn.attr == func_name:
            results.append(node)
    return results


def uses_name(tree: ast.AST, name: str) -> list[ast.AST]:
    """Return every ``ast.Name`` (or ``Attribute.attr``) matching ``name``."""
    hits: list[ast.AST] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == name:
            hits.append(node)
        elif isinstance(node, ast.Attribute) and node.attr == name:
            hits.append(node)
    return hits


def call_kwargs(call: ast.Call) -> dict[str, ast.AST]:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def first_line(node: ast.AST) -> int:
    return getattr(node, "lineno", -1)


def list_literal(node: ast.AST) -> list[str] | None:
    """Extract a literal list of strings from an AST node, if shape matches."""
    if not isinstance(node, ast.List):
        return None
    out: list[str] = []
    for el in node.elts:
        if isinstance(el, ast.Constant) and isinstance(el.value, str):
            out.append(el.value)
        else:
            return None
    return out


def module_docstring(tree: ast.AST) -> str | None:
    if not isinstance(tree, ast.Module) or not tree.body:
        return None
    first = tree.body[0]
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        return first.value.value
    return None


# ---------------------------------------------------------------------------
# YAML helpers
# ---------------------------------------------------------------------------


def load_yaml(path: Path) -> dict | list | None:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None


def yaml_byte_diff(path_a: Path, path_b: Path) -> bool:
    """True if the two files differ byte-for-byte (or either is missing)."""
    if not path_a.is_file() or not path_b.is_file():
        return True
    return path_a.read_bytes() != path_b.read_bytes()
