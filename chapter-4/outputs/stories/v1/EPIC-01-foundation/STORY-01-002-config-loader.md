# STORY-01-002: Implement Configuration Loader

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 3 |
| **Sprint** | Sprint 1 |
| **Dependencies** | STORY-01-001 |
| **Status** | To Do |

## User Story

As a data engineer, I want a configuration loader that reads YAML configs and resolves environment-specific overrides so that all pipeline modules use consistent settings across DEV, STAGING, and PROD.

## Description

Implement `src/config/pipeline_config.py` that loads the pipeline YAML configuration file and resolves environment-specific overrides. The loader must support the full parameter inventory defined in LLD Section 7.1 including scheduling, compute, storage, retry, alerting, monitoring, catalog, and ingestion parameters. Environment selection is driven by an environment variable (e.g., `PIPELINE_ENV=DEV|STAGING|PROD`). The loader should validate required parameters are present and raise clear errors for missing or invalid configuration.

## Acceptance Criteria

- [ ] `pipeline_config.py` loads YAML config file and parses all parameters from LLD SS7.1 [LLD §7.1]
- [ ] Environment-specific overrides resolve correctly for DEV, STAGING, and PROD [LLD §7.2]
- [ ] Missing required parameters raise `ConfigurationError` with descriptive message [LLD §7]
- [ ] Config loader returns a typed dataclass or dictionary with dot-notation access [LLD §2.2]
- [ ] Unit tests cover: valid config load, missing parameter error, environment override resolution [LLD §2.4]

## Technical Notes

- **Upstream references**: LLD SS7 (Configuration Schema), LLD SS7.1 (Parameter Inventory), LLD SS7.2 (Environment Overrides)
- **Implementation hints**: Use `pyyaml` for YAML parsing. Consider a `@dataclass` for typed config access. Reference the generated `config/config-template.yaml` for the full structure. The ingestion framework parameters (`ingestion.config_dir`, `ingestion.dq_rules_file`, etc.) must be included.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS7 (Configuration Schema), SS7.1, SS7.2 |
| DMS | -- |
| STM | -- |
| DQS | -- |
