"""Execute guarded SELECT queries against the Gold tables via Spark + Unity Catalog.

Uses the pipeline's own :func:`patient_360.utils.delta_helpers.build_spark_session`, so the
agent reads ``unity.gold.*`` exactly as the pipeline writes it (same catalog wiring, same
Spark SQL dialect the semantic model advertises). The session is built lazily and reused.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

# Delta + Unity Catalog connector jars the driver needs to read unity.gold.* Delta tables.
# These mirror the pipeline's spark-submit packages (LLD Decision 3); OpenLineage is omitted
# because the read-only agent emits no lineage. A bare `python` driver has no --packages, so
# the executor supplies them via spark.jars.packages (Ivy resolves/caches them on first use).
_READ_PACKAGES = (
    "io.delta:delta-spark_2.13:4.3.0",
    "io.unitycatalog:unitycatalog-spark_4.1_2.13:0.5.0",
)


@dataclass(frozen=True)
class QueryResult:
    """Columnar result of a query."""

    columns: list[str]
    rows: list[tuple[Any, ...]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


class GoldExecutor(Protocol):
    """The execution surface the agent depends on (fakeable in tests)."""

    def run(self, sql: str) -> QueryResult: ...


class SparkGoldExecutor:
    """Run read-only SQL against ``unity.gold.*`` on a reused Spark session."""

    def __init__(
        self,
        spark: Any | None = None,
        *,
        app_name: str = "patient360-semantic-agent",
        max_rows: int = 1000,
    ) -> None:
        self._spark = spark
        self._app_name = app_name
        self._max_rows = max_rows

    def _session(self) -> Any:
        if self._spark is None:
            from patient_360.utils.delta_helpers import build_spark_session

            self._spark = build_spark_session(
                self._app_name,
                extra_conf={
                    "spark.jars.packages": ",".join(_READ_PACKAGES),
                    # Interactive agent (REPL): silence the per-query [Stage N:===] bars.
                    "spark.ui.showConsoleProgress": "false",
                },
            )
            # Drop JVM chatter (INFO/WARN) once the context exists; keep ERROR so real
            # failures still surface. Overridable via SEMANTIC_SPARK_LOG_LEVEL.
            level = os.environ.get("SEMANTIC_SPARK_LOG_LEVEL", "ERROR")
            self._spark.sparkContext.setLogLevel(level)
        return self._spark

    def run(self, sql: str) -> QueryResult:
        df = self._session().sql(sql)
        columns = list(df.columns)
        rows = [tuple(row) for row in df.limit(self._max_rows).collect()]
        return QueryResult(columns=columns, rows=rows)

    def stop(self) -> None:
        if self._spark is not None:
            self._spark.stop()
            self._spark = None


