"""Render a :class:`SemanticModel` into the text block an NL-to-SQL agent injects.

The output is compact Markdown (tables, measures-as-SQL, join graph, glossary, few-shot
verified queries) plus a short list of hard rules that keep generated SQL correct against
this specific Gold layer (exact literals, cost isolation, encounter fan-out, empty columns).
"""

from __future__ import annotations

from jinja2 import Environment

from patient_360.semantic.schema import SemanticModel

# The module is dominated by a Jinja template literal whose text/rule lines are intentionally
# long (they render as single prompt lines); line-length does not apply to that content.
# ruff: noqa: E501

_TEMPLATE = """\
# Semantic model: {{ m.name }}  (dialect: {{ m.dialect }})
{{ m.description | trim }}

Query the physical tables by their fully-qualified names ({{ m.catalog }}.gold.*). All Gold
tables are full-overwrite current snapshots (no `ds` partition, no date filter needed).

## Tables
{% for e in m.entities %}
### {{ e.table }}
- Grain: {{ e.grain }}
- Primary key: `{{ e.primary_key }}`
  {%- if e.synonyms %} | Also called: {{ e.synonyms | join(", ") }}{% endif %}
{%- if e.description %}
- {{ e.description | trim }}
{%- endif %}

Dimensions (column | sample values | notes):
{% for d in e.dimensions -%}
- `{{ d.column }}` ({{ d.type or "?" }})
  {%- if d.sensitive %} [SENSITIVE/PHI]{% endif %}
  {%- if not d.present_in_data %} [NO DATA IN CURRENT LOAD]{% endif %}
  {%- if d.description %} — {{ d.description | trim }}{% endif %}
  {%- if d.sample_values %} | values: {{ d.sample_values | join(", ") }}{% endif %}
  {%- if d.synonyms %} | aka: {{ d.synonyms | join(", ") }}{% endif %}
{% endfor -%}
{% if e.measures %}
Measures (name = SQL):
{% for me in e.measures -%}
- {{ me.name }} = `{{ me.to_sql() }}`
  {%- if not me.present_in_data %} [EMPTY IN CURRENT LOAD]{% endif %}
  {%- if me.description %} — {{ me.description | trim }}{% endif %}
{% endfor -%}
{% endif %}
{%- if e.notes %}
Caveats:
{% for n in e.notes -%}
- {{ n | trim }}
{% endfor -%}
{% endif %}
{% endfor %}
## Joins
{% for r in m.relationships -%}
- {{ r.from_entity }}.`{{ r.from_column }}` -> {{ r.to_entity }}.`{{ r.to_column }}` ({{ r.cardinality.value }})
  {%- if r.description %} — {{ r.description | trim }}{% endif %}
{% endfor %}
{% if m.metrics %}## Named metrics
{% for mt in m.metrics -%}
- {{ mt.name }} — {{ mt.description | trim }} (on {{ mt.entity }}: {{ mt.measure }}
  {%- if mt.group_by %} by {{ mt.group_by | join(", ") }}{% endif %}
  {%- if mt.filter %} where {{ mt.filter }}{% endif %})
{% endfor %}
{% endif %}
{% if m.glossary %}## Glossary (business term -> SQL)
{% for term, meaning in m.glossary.items() -%}
- {{ term }} -> {{ meaning }}
{% endfor %}
{% endif %}
{% if m.verified_queries %}## Verified example queries
{% for vq in m.verified_queries -%}
Q: {{ vq.question }}
{% if vq.description %}({{ vq.description | trim }})
{% endif %}```sql
{{ vq.sql | trim }}
```
{% endfor %}
{% endif %}
## Rules for generating SQL
- Use ONLY the tables and columns listed above; reference tables by their full name ({{ m.catalog }}.gold.*).
- Use the EXACT literal values shown under "values" (they are case- and code-sensitive, e.g. marital_status is a single letter). Map business words via the glossary.
- Cost/financial columns exist ONLY on patient_billing_summary.
- When counting encounters on patient_billing_summary use COUNT(DISTINCT encounter_id) (claims can fan out).
- Columns/measures tagged [NO DATA IN CURRENT LOAD] / [EMPTY IN CURRENT LOAD] will return null/0 — say so rather than inventing results.
- This is {{ m.dialect }}; return a single SELECT statement.
"""


def render_context(model: SemanticModel) -> str:
    """Render ``model`` into the prompt-ready context string."""
    env = Environment(trim_blocks=False, lstrip_blocks=False, autoescape=False)
    template = env.from_string(_TEMPLATE)
    # Collapse the runs of blank lines the template's control blocks can leave behind.
    rendered = template.render(m=model)
    lines = [ln.rstrip() for ln in rendered.splitlines()]
    out: list[str] = []
    for ln in lines:
        if ln == "" and out and out[-1] == "":
            continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"
