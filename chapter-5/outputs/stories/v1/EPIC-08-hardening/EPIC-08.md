# EPIC-08: Hardening — Security, Documentation, Maintenance

| Field | Value |
|-------|-------|
| **LLD Section** | §8.7, §3.4 |
| **Epic Scope** | crosscut |
| **Stories** | 3 |
| **Total Points** | 9 |
| **Sprints** | 6 |
| **Status** | To Do |

## Objective

System-wide hardening: PHI / security audit (no plain-text PHI in logs, dead-letter, or non-warehouse paths), documentation + coverage audit (READMEs current, ≥ 90% coverage), and Delta VACUUM/OPTIMIZE maintenance schedule per LLD §3.4.

## Scope

### In Scope
- PHI / log scrubbing audit
- Documentation + ≥ 90% coverage audit across the codebase
- Delta VACUUM / OPTIMIZE maintenance Airflow DAG (separate from hourly pipeline)

### Out of Scope
- Layer-specific perf (lives in EPIC-02..05)
- CI/CD (EPIC-07)

## Stories

| ID | Title | Type | Points | Sprint | Dependencies |
|----|-------|------|--------|--------|-------------|
| STORY-08-001 | PHI / security audit — log scrubbing + dead-letter inspection | hardening | 3 | 6 | STORY-07-004 |
| STORY-08-002 | Documentation + coverage audit (≥ 90%) | hardening | 3 | 6 | STORY-07-001 |
| STORY-08-003 | Delta VACUUM / OPTIMIZE maintenance DAG | hardening | 3 | 6 | STORY-07-003 |

## Acceptance Criteria (Epic-Level)

- [ ] Security audit signed off — no PHI in logs / dead-letter (other than `_raw_record`) [LLD §8.4]
- [ ] All READMEs reviewed; coverage ≥ 90% line per LLD §9.3 [LLD §9.3]
- [ ] Maintenance DAG runs nightly: VACUUM (168h retention) + OPTIMIZE on Bronze/Silver/Gold per LLD §3.4 [LLD §3.4]

## Risks & Assumptions

- Production freeze week (team-capacity §5) — schedule maintenance DAG outside the freeze
- Allergy `_error` table extended retention (90 days) per DRD §1.3
