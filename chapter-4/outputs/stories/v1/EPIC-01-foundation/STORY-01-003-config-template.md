# STORY-01-003: Create Configuration Template YAML

| Field | Value |
|-------|-------|
| **Epic** | EPIC-01: Foundation |
| **Priority** | P1 -- Critical Path |
| **Story Points** | 2 |
| **Sprint** | Sprint 1 |
| **Dependencies** | STORY-01-002 |
| **Status** | To Do |

## User Story

As a data engineer, I want a validated configuration template with all three environment profiles so that I can deploy the pipeline to DEV, STAGING, and PROD with correct settings.

## Description

Create `config/config-template.yaml` with all parameters defined in LLD Section 7.1 across DEV, STAGING, and PROD environments. This includes scheduling, compute resources (Spark driver/executor memory, cores, shuffle partitions), storage paths (base path, dead-letter, checkpoints), catalog settings (Unity Catalog OSS URL, catalog name, warehouse path), retry policies, alerting channels, monitoring endpoints, and ingestion framework settings. The template must be a valid YAML file that the config loader from STORY-01-002 can parse without errors.

## Acceptance Criteria

- [ ] `config/config-template.yaml` contains all parameters from LLD SS7.1 [LLD §7.1]
- [ ] DEV, STAGING, and PROD environment sections present with correct values [LLD §7.2]
- [ ] Ingestion framework section includes config_dir, dq_rules_file, dq_rules_convention, and inline_se settings [LLD §2.3]
- [ ] Config template loads successfully through the config loader from STORY-01-002 [LLD §7]
- [ ] YAML is well-formed and commented for operator usability [LLD §7]

## Technical Notes

- **Upstream references**: LLD SS7 (Configuration Schema), config-template.yaml (derived artifact)
- **Implementation hints**: Use the generated `outputs/lld/v1/config/config-template.yaml` as the reference. Ensure all localhost endpoints match infrastructure-specs.md SS4.

## Estimation Support

| Artifact | Sections Covered |
|----------|-----------------|
| LLD | SS7 (Configuration Schema), SS7.1, SS7.2 |
| HLD | SS5.1 (Technology Stack) |
| DMS | -- |
| DQS | -- |
