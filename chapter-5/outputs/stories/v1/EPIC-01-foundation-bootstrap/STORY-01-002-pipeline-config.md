# STORY-01-002: Implement pipeline_config loader and logging utilities

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation & Runtime Bootstrap |
| **Story Type** | build |
| **Priority** | P1 |
| **Story Points** | 3 |
| **Sprint** | 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a Data Engineer, I want a centralized config loader and structured logging so that every pipeline module reads parameters consistently from `_infra/cd/config/{env}.yaml` and emits parseable logs.

## Description

Implement `src/patient_360/utils/pipeline_config.py` exposing a `load_config(env: str) -> dict` function that reads YAML from `_infra/cd/config/{env}.yaml` and merges base + env overrides per LLD §7.2. Implement `src/patient_360/utils/logging_config.py` exposing `get_logger(name)` with structured JSON logging configured. Both modules ship with unit tests under `tests/utils/`.

## Acceptance Criteria

- [ ] `patient_360/src/patient_360/utils/pipeline_config.py` exposes `load_config(env)` that loads `_infra/cd/config/{env}.yaml` [LLD §7.1, §7.2]
- [ ] `patient_360/src/patient_360/utils/logging_config.py` exposes `get_logger(name)` returning a configured stdlib logger [LLD §10.1]
- [ ] All 35 parameters from LLD §7.1 are accessible via dotted-path lookup [LLD §7.1]
- [ ] `patient_360/tests/utils/test_pipeline_config.py` exercises load + override merge

## Technical Notes

- **Upstream references**: LLD §7.1 Parameter Inventory, §7.2 Environment Overrides, §10.1 Metrics
- **Implementation hints**: Use `pyyaml`. Config keys are dot-separated per LLD §2.2 conventions (`pipeline.bronze.batch_size`).

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | §7.1, §7.2, §10.1 |
| DMS | — |
| STM | — |
| DQS | — |

## Testing

| Coverage | What | How |
|----------|------|-----|
| Unit | load_config merges base + env overrides | `pytest patient_360/tests/utils/test_pipeline_config.py` |
| Unit | get_logger returns configured logger | `pytest patient_360/tests/utils/test_logging_config.py` |

## Verification

```yaml
AC1:
  - file_exists: "patient_360/src/patient_360/utils/pipeline_config.py"
  - grep: {file: "patient_360/src/patient_360/utils/pipeline_config.py", pattern: 'def load_config'}
AC2:
  - file_exists: "patient_360/src/patient_360/utils/logging_config.py"
  - grep: {file: "patient_360/src/patient_360/utils/logging_config.py", pattern: 'def get_logger'}
AC3:
  - manual: "review pipeline_config.py supports all 35 §7.1 parameters via dotted-path"
AC4:
  - pytest: {node: "patient_360/tests/utils/test_pipeline_config.py"}
```

## How to Test (User)

### Prerequisites

- STORY-01-001 complete (`patient_360/` rendered)
- `make dev-setup` completed

### Steps

1. `cd patient_360 && uv run python -c "from patient_360.utils.pipeline_config import load_config; print(load_config('dev'))"`
2. `cd patient_360 && uv run pytest tests/utils/ -v`

### Expected outcome

- Step 1 prints a dict containing keys like `compute.spark_driver_memory`
- Step 2 reports all tests passing

## Documentation Updates

- [ ] N/A — internal utility module, not user-facing
