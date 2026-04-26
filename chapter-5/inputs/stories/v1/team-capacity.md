# Team Capacity — Patient 360 Data Pipeline

| Field | Value |
|-------|-------|
| **Document Version** | 1.0 |
| **Last Updated** | 2026-03-23 |
| **Author** | Engineering Manager |
| **Applicable Project** | Patient 360 |

---

## 1. Sprint Configuration

| Parameter | Value | Notes |
|-----------|-------|-------|
| Sprint Length | 2 weeks | Standard 10 business days |
| Sprint Cadence | Bi-weekly | Monday start, Friday end |
| Ceremonies Overhead | 1 day/sprint | Planning, review, retro, standups |
| Available Dev Days | 9 days/sprint | Per developer |

---

## 2. Team Composition

| Role | Name | Allocation | Skills |
|------|------|------------|--------|
| Senior Data Engineer | Alex M. | 100% | Python, SQL, DuckDB, Spark, Airflow |
| Data Engineer | Jordan K. | 100% | Python, SQL, DuckDB, dbt |
| Data Engineer | Sam R. | 50% | Python, SQL, shared with another project |
| QA / Data Quality | Taylor P. | 50% | Python, Great Expectations, testing |

**Effective FTE**: 3.0 (2 full + 2 half)

---

## 3. Velocity Estimates

| Metric | Value | Basis |
|--------|-------|-------|
| Estimated Velocity | 25-30 points/sprint | Based on team size and complexity |
| Story Point Scale | Fibonacci (1, 2, 3, 5, 8, 13) | 1 = trivial, 13 = full sprint |
| Max Single Story | 8 points | Stories > 8 must be split |
| Target Utilization | 80% | Buffer for unplanned work |

---

## 4. Skills Matrix

| Skill Area | Alex M. | Jordan K. | Sam R. | Taylor P. |
|-----------|---------|-----------|--------|-----------|
| DuckDB / SQL | Expert | Proficient | Proficient | Basic |
| Python ETL | Expert | Proficient | Proficient | Proficient |
| Data Modeling | Proficient | Basic | Basic | — |
| Data Quality | Proficient | Basic | Basic | Expert |
| CI/CD / Deployment | Proficient | Basic | — | Basic |
| Monitoring / Observability | Basic | — | — | Proficient |

---

## 5. Constraints & Availability

| Constraint | Impact |
|-----------|--------|
| Sam R. at 50% allocation | Cannot be assigned blocking stories |
| Taylor P. at 50% allocation | DQ stories should be batched for efficiency |
| No Spark expertise beyond Alex | Spark-related stories need Alex as owner |
| Production freeze: last week of quarter | No deployments in that window |
