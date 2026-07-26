"""File-based semantic model over the Gold layer.

A tailored, self-contained semantic layer that grounds natural-language-to-SQL
generation against the ``unity.gold.*`` tables. The YAML under ``semantic/`` is the
source of truth for *business* meaning (grain, dimensions, measures, joins, metrics,
synonyms, verified example queries); the physical column contract stays in
``contracts/*.yml`` and is used as the drift oracle by :mod:`patient_360.semantic.validate`.

Public surface:

- :class:`~patient_360.semantic.schema.SemanticModel` and its sub-models.
- :func:`~patient_360.semantic.loader.load_model` — parse the ``semantic/`` directory.
- :func:`~patient_360.semantic.render.render_context` — render the LLM prompt block.
- :func:`~patient_360.semantic.validate.validate_model` — cross-check against contracts.
"""

from patient_360.semantic.agent import AgentResult, SemanticSQLAgent, build_default_agent
from patient_360.semantic.executor import QueryResult, SparkGoldExecutor
from patient_360.semantic.llm import (
    LiteLLMClient,
    LLMClient,
    Message,
    build_llm_from_env,
)
from patient_360.semantic.loader import DEFAULT_SEMANTIC_DIR, load_model
from patient_360.semantic.render import render_context
from patient_360.semantic.schema import (
    Dimension,
    Entity,
    Measure,
    Metric,
    Relationship,
    SemanticModel,
    VerifiedQuery,
)
from patient_360.semantic.sql_guard import GuardError, extract_sql, guard_sql
from patient_360.semantic.validate import Finding, Severity, validate_model

__all__ = [
    "DEFAULT_SEMANTIC_DIR",
    "AgentResult",
    "Dimension",
    "Entity",
    "Finding",
    "GuardError",
    "LLMClient",
    "LiteLLMClient",
    "Measure",
    "Message",
    "Metric",
    "QueryResult",
    "Relationship",
    "SemanticModel",
    "SemanticSQLAgent",
    "Severity",
    "SparkGoldExecutor",
    "VerifiedQuery",
    "build_default_agent",
    "build_llm_from_env",
    "extract_sql",
    "guard_sql",
    "load_model",
    "render_context",
    "validate_model",
]
