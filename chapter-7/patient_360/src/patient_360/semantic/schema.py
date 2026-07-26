"""Pydantic models for the file-based semantic model.

These types are intentionally generic (nothing patient-360 specific lives here) so the
loader/validator/renderer can be reused for any project's semantic layer — the YAML
files carry the project data. See ``semantic/manifest.yml`` and ``semantic/entities/``.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AggKind(StrEnum):
    """Aggregation applied to a measure's ``expr`` when it is projected in SQL."""

    COUNT = "count"
    COUNT_DISTINCT = "count_distinct"
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    # ``custom`` — ``expr`` is a full aggregate SQL fragment used verbatim
    # (e.g. ``AVG(CASE WHEN has_30day_readmission_history THEN 1 ELSE 0 END)``).
    CUSTOM = "custom"


class Cardinality(StrEnum):
    """Join cardinality of a relationship, read ``from`` -> ``to``."""

    MANY_TO_ONE = "many_to_one"
    ONE_TO_ONE = "one_to_one"
    ONE_TO_MANY = "one_to_many"


class _Base(BaseModel):
    # Reject unknown keys so a typo in the YAML fails loudly instead of being ignored.
    model_config = ConfigDict(extra="forbid")


class Dimension(_Base):
    """A groupable / filterable attribute exposed to the NL-to-SQL agent."""

    name: str
    column: str
    type: str | None = None
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    sample_values: list[str] = Field(default_factory=list)
    # False => the column exists in the schema but carries no data in the current load;
    # the renderer surfaces this so the agent does not build answers on empty columns.
    present_in_data: bool = True
    sensitive: bool = False
    notes: list[str] = Field(default_factory=list)


class Measure(_Base):
    """A numeric aggregation the agent may compute."""

    name: str
    agg: AggKind
    expr: str | None = None
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    present_in_data: bool = True
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _expr_required_unless_count(self) -> Measure:
        # Only a plain COUNT(*) may omit expr; every other agg needs a column/expression.
        if self.agg is not AggKind.COUNT and not self.expr:
            raise ValueError(f"measure {self.name!r}: agg {self.agg.value!r} requires 'expr'")
        return self

    def to_sql(self) -> str:
        """Render this measure as a SQL aggregate expression."""
        if self.agg is AggKind.CUSTOM:
            return self.expr or ""
        if self.agg is AggKind.COUNT_DISTINCT:
            return f"COUNT(DISTINCT {self.expr})"
        if self.agg is AggKind.COUNT:
            return f"COUNT({self.expr or '*'})"
        return f"{self.agg.value.upper()}({self.expr})"


class Entity(_Base):
    """One Gold table and its business meaning."""

    name: str
    table: str
    grain: str
    primary_key: str
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    sensitive_columns: list[str] = Field(default_factory=list)
    dimensions: list[Dimension] = Field(default_factory=list)
    measures: list[Measure] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("dimensions")
    @classmethod
    def _unique_dimension_names(cls, dims: list[Dimension]) -> list[Dimension]:
        names = [d.name for d in dims]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate dimension names: {sorted(dupes)}")
        return dims

    @field_validator("measures")
    @classmethod
    def _unique_measure_names(cls, measures: list[Measure]) -> list[Measure]:
        names = [m.name for m in measures]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate measure names: {sorted(dupes)}")
        return measures

    def dimension(self, name: str) -> Dimension | None:
        return next((d for d in self.dimensions if d.name == name), None)

    def measure(self, name: str) -> Measure | None:
        return next((m for m in self.measures if m.name == name), None)

    def has_column(self, column: str) -> bool:
        if column == self.primary_key:
            return True
        return any(d.column == column for d in self.dimensions)


class Relationship(_Base):
    """A join between two entities, expressed on their business columns."""

    name: str | None = None
    from_entity: str
    from_column: str
    to_entity: str
    to_column: str
    cardinality: Cardinality = Cardinality.MANY_TO_ONE
    description: str = ""


class Metric(_Base):
    """A named business metric: a measure evaluated on an entity, optionally grouped/filtered."""

    name: str
    entity: str
    measure: str
    description: str = ""
    group_by: list[str] = Field(default_factory=list)
    filter: str | None = None
    synonyms: list[str] = Field(default_factory=list)


class VerifiedQuery(_Base):
    """A curated NL question and its known-good SQL, used for few-shot grounding."""

    question: str
    sql: str
    description: str = ""


class SemanticModel(_Base):
    """The whole semantic model: entities + relationships + metrics + glossary + examples."""

    name: str
    description: str = ""
    version: str = "1.0"
    dialect: str = "Spark SQL"
    catalog: str | None = None
    entities: list[Entity]
    relationships: list[Relationship] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    # business term -> plain-English meaning / coded-value mapping (e.g. "married -> 'M'")
    glossary: dict[str, str] = Field(default_factory=dict)
    verified_queries: list[VerifiedQuery] = Field(default_factory=list)

    @field_validator("entities")
    @classmethod
    def _unique_entity_names(cls, entities: list[Entity]) -> list[Entity]:
        if not entities:
            raise ValueError("a semantic model needs at least one entity")
        names = [e.name for e in entities]
        dupes = {n for n in names if names.count(n) > 1}
        if dupes:
            raise ValueError(f"duplicate entity names: {sorted(dupes)}")
        return entities

    def entity(self, name: str) -> Entity | None:
        return next((e for e in self.entities if e.name == name), None)

    def entity_by_table(self, table: str) -> Entity | None:
        return next((e for e in self.entities if e.table == table), None)

    def tables(self) -> list[str]:
        return [e.table for e in self.entities]
