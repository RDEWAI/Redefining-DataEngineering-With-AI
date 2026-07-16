# Development Standards

| Field | Value |
|-------|-------|
| **Version** | 1.0 |
| **Last Updated** | 2026-03-22 |
| **Owner** | Engineering Lead |
| **Applies To** | Patient 360 Data Pipeline |

---

## 1. Language & Runtime

| Component | Standard | Version |
|-----------|----------|---------|
| Primary Language | Python | 3.10–3.12 |
| Data Processing | PySpark | 3.5.x |
| SQL Dialect | Spark SQL / DuckDB SQL | — |
| Package Manager | UV | Latest |

---

## 2. Code Organization

### 2.1 Project Structure

```
src/
├── pipelines/
│   ├── bronze/          # Ingestion tasks (1 module per source table)
│   ├── silver/          # Transformation tasks (1 module per target table)
│   └── gold/            # Denormalization tasks (1 module per consumer table)
├── transforms/          # Shared transformation functions
├── quality/             # DQ rule implementations
├── config/              # Configuration loaders and schemas
└── utils/               # Shared utilities (logging, metrics, etc.)
tests/
├── unit/                # Unit tests (mocked I/O)
├── integration/         # Integration tests (real DuckDB/Delta)
└── fixtures/            # Test data fixtures
```

### 2.2 Naming Conventions

| Element | Convention | Example |
|---------|-----------|---------|
| Module files | `snake_case.py` | `ingest_patients.py` |
| Classes | `PascalCase` | `BronzeIngestionTask` |
| Functions | `snake_case` | `load_encounters()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_RETRY_COUNT` |
| Config keys | `dot.separated` | `pipeline.bronze.batch_size` |

---

## 3. Linting & Formatting

| Tool | Purpose | Configuration |
|------|---------|---------------|
| Ruff | Linting + formatting | `ruff.toml` at repo root |
| Ruff format | Code formatting | Line length: 100 |
| mypy | Type checking | `--strict` for new modules |

Rules: Follow PEP 8. All new code must pass `ruff check` and `ruff format --check`.

---

## 4. Git Strategy

| Aspect | Standard |
|--------|----------|
| Branching model | Feature branches off `main` |
| Branch naming | `feature/{ticket}-{short-desc}` |
| Commit messages | Conventional Commits (`feat:`, `fix:`, `refactor:`) |
| PR requirements | 1 approval, all tests pass, no lint errors |
| Merge strategy | Squash merge to `main` |

---

## 5. Testing Requirements

| Category | Coverage Target | Framework |
|----------|----------------|-----------|
| Unit tests | ≥ 90% line coverage | pytest |
| Integration tests | All pipeline paths | pytest + Unity Catalog OSS |
| DQ rule tests | 100% of CRITICAL rules | pytest |

### 5.1 Test Naming Convention

```
test_{layer}_{operation}_{scenario}
# Example: test_bronze_ingest_patients_null_id_rejected
```

---

## 6. Logging Standards

| Aspect | Standard |
|--------|----------|
| Format | Structured JSON |
| Library | Python `logging` with JSON formatter |
| Log levels | DEBUG (dev), INFO (prod default), WARNING/ERROR |
| Required fields | `timestamp`, `level`, `task_name`, `pipeline_run_id`, `message` |
| Sensitive data | NEVER log PHI/PII — use masked references only |

---

## 7. Documentation

| Document | When Required |
|----------|---------------|
| Docstrings | All public functions and classes |
| README | Each pipeline module directory |
| CHANGELOG | Each release |
| Architecture Decision Records | Major technical decisions |
