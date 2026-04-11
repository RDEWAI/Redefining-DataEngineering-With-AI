# Story Standards — Patient 360 Data Pipeline

| Field | Value |
|-------|-------|
| **Document Version** | 1.0 |
| **Last Updated** | 2026-03-23 |
| **Author** | Scrum Master |
| **Applicable Project** | Patient 360 |

---

## 1. Story Template

Every story MUST follow this structure:

### Required Sections
1. **User Story** — "As a {persona}, I want {goal} so that {benefit}"
2. **Description** — Detailed technical description (minimum 3 sentences)
3. **Acceptance Criteria** — Checkboxes with upstream artifact references
4. **Technical Notes** — Implementation hints, upstream references
5. **Estimation Support** — Table mapping to DMS/STM/DQS/LLD sections

### Optional Sections
- **Mockup / Diagram** — Visual aid if applicable
- **Out of Scope** — What this story explicitly does NOT cover

---

## 2. Definition of Done

A story is "Done" when ALL of the following are met:

| # | Criterion | Verifier |
|---|-----------|----------|
| 1 | Code committed to feature branch | Developer |
| 2 | Unit tests written and passing | Developer |
| 3 | Integration test passing (if applicable) | Developer |
| 4 | DQ rules implemented per DQS reference | QA |
| 5 | Code reviewed by at least 1 peer | Reviewer |
| 6 | Documentation updated (if applicable) | Developer |
| 7 | Deployed to staging environment | CI/CD |

---

## 3. Acceptance Criteria Format

Acceptance criteria MUST:
- Use checkbox format: `- [ ] Criterion text [Upstream §X.Y]`
- Reference at least one upstream artifact section
- Be testable / verifiable (not vague)
- Use active voice ("Table contains..." not "Table should contain...")

### Examples

**Good:**
```
- [ ] bronze_patients table created with 12 columns matching DMS §4.2
- [ ] Null patient_id records rejected per DQS §3.1.1
- [ ] Ingestion completes within 5-minute SLA per HLD §5.4
```

**Bad:**
```
- [ ] Data is loaded correctly
- [ ] Quality checks pass
- [ ] Everything works
```

---

## 4. Story Sizing Guidelines

| Points | Complexity | Example |
|--------|-----------|---------|
| 1 | Trivial — config change, simple fix | Update a YAML config value |
| 2 | Small — single table, straightforward | Create one bronze table DDL |
| 3 | Medium — multi-step, one domain | Bronze ingestion for 3 related tables |
| 5 | Large — cross-domain, some complexity | Silver transformation with business rules |
| 8 | Very large — max allowed per story | Gold dimensional model with SCD Type 2 |
| 13 | Too large — MUST be split | Never assign 13 points |

---

## 5. Priority Scheme

| Priority | Definition | Sprint Placement |
|----------|-----------|-----------------|
| P1 — Critical Path | Blocks other stories; no workaround | Sprint 1-2 |
| P2 — Important | Needed for completeness; has workaround | Sprint 2-3 |
| P3 — Nice to Have | Improves quality or DX; can defer | Sprint 3+ |
