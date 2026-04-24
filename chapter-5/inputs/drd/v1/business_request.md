# Business Request: Patient 360 Search

**Submitted by**: Dr. Sarah Chen, Chief Medical Officer
**Date**: January 2026
**Priority**: High

## Problem Statement

Our clinicians currently navigate three to five separate systems to piece together
a complete picture of a patient before each appointment. Electronic health records
are in one system, lab results in another, billing history in a third, and allergy
data in yet another. On average, a physician spends 8 minutes per patient just
finding and cross-referencing information across these systems.

This fragmented workflow creates several problems:
- Clinicians are frustrated by the time wasted on lookups
- Critical information (allergies, recent lab results) is sometimes missed
- Care coordinators cannot efficiently identify care gaps across their patient panels
- Billing staff spend excessive time reconciling encounter and claims data

## Desired Outcome

We want a **Patient 360 experience** — a single search interface where any authorized
staff member can type a patient's name and instantly see a complete, consolidated view
of that patient. Think of it like a Google search, but for patient data.

When a user searches for "John Smith", the system should return:
- Patient demographics (name, date of birth, address, contact information)
- Recent encounters (last 12 months of visits, with dates, types, and reasons)
- Active diagnoses and conditions
- Current medications (what they're taking, dosages, prescribing dates)
- Recent lab results and vitals
- Known allergies (prominently displayed for safety)
- Billing summary (recent claims, outstanding balances)

## Target Users

| User Group | Estimated Count | Primary Need |
|------------|----------------|--------------|
| Physicians | 120 | Pre-appointment review, point-of-care lookup |
| Nurses | 200 | Medication verification, allergy checks |
| Care Coordinators | 30 | Panel management, care gap identification |
| Billing Staff | 50 | Claims verification, payment tracking |
| Department Heads | 15 | Utilization reporting |

## Business Objectives

1. Reduce clinician time spent on patient lookups from 8 minutes to under 30 seconds
2. Eliminate missed allergy alerts by surfacing them prominently in every search result
3. Enable care coordinators to review 30+ patients per day (up from 10-15 currently)
4. Provide billing staff with instant access to encounter-claims reconciliation
5. Support quality reporting by making readmission data easily accessible

## Success Metrics

- 90% of searches return complete results within 2 seconds
- Clinician satisfaction score above 4.0 out of 5.0 in post-launch survey
- 50% reduction in pre-appointment chart review time
- Zero missed allergy alerts in the first 90 days
- All active patients (~1,000 in current system) searchable from day one

## Timeline

- Phase 1 (current): Build the data foundation — consolidate data from source systems
- Phase 2: Develop the search interface
- Phase 3: Roll out to pilot group (20 physicians, 10 nurses)
- Phase 4: Hospital-wide launch

## Budget and Constraints

- This project is funded through the Health IT improvement budget
- Must use existing data infrastructure where possible (DuckDB analytics database)
- No new system purchases in Phase 1 — leverage current Synthea-based data
- HIPAA compliance is required; security architecture will be a separate workstream
