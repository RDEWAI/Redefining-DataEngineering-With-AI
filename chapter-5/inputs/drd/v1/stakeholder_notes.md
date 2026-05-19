# Stakeholder Interview Notes: Patient 360

## Interview 1: Dr. Sarah Chen — Chief Medical Officer

**Date**: January 15, 2026
**Interviewer**: Business Analyst

### Key Points

- Primary concern is **patient safety**. Allergies must be the first thing a clinician
  sees when looking up a patient. "If we miss an allergy because the data was buried,
  that is a patient safety failure."
- Wants a **clinical summary** at the top of each patient view: active conditions,
  current medications, recent encounter date.
- Lab results should show the **most recent value** for each test type by default,
  with the ability to see historical trends.
- Readmission tracking is critical for quality reporting. Any patient readmitted
  within 30 days of discharge should be flagged automatically.
- Data must be **no more than 1 hour old** for clinical use. Stale data is
  dangerous in a clinical setting.

### Requirements

- Allergy alerts: displayed prominently, with severity level (if known)
- Clinical summary: active conditions, medications, last encounter date
- Lab results: most recent per test, with option to see history
- Readmission flag: 30-day window, inpatient encounters only
- Data latency: maximum 1 hour for clinical data

---

## Interview 2: Michael Torres — Chief Information Officer

**Date**: January 16, 2026
**Interviewer**: Business Analyst

### Key Points

- All patient data currently lives in the **Synthea-based DuckDB database**
  under the `synthea` schema. This is the single source of truth.
- The database has 18 tables covering patients, encounters, conditions,
  medications, observations, procedures, allergies, immunizations, claims,
  careplans, payers, organizations, providers, devices, supplies, and imaging.
- System must handle **concurrent lookups** from 400+ staff during peak hours
  (7-9 AM, 12-1 PM).
- Concerned about **search performance**. Name-based search must return results
  in under 2 seconds, even with fuzzy matching.
- Role-based access control (RBAC) is essential but can be Phase 2. For now,
  focus on getting the data consolidated.
- System availability: 99.5% uptime during business hours (6 AM to 10 PM).

### Requirements

- Single data source: DuckDB `synthea` schema
- Performance: sub-2-second search for 90th percentile
- Concurrency: support 400+ simultaneous users
- Availability: 99.5% during 6 AM - 10 PM
- RBAC: defer to Phase 2

---

## Interview 3: Lisa Park — Clinical Operations Manager

**Date**: January 17, 2026
**Interviewer**: Business Analyst

### Key Points

- Care coordinators currently manage panels of 50-100 patients each.
  They need to review each patient quarterly for **care gaps** (overdue
  screenings, missed follow-ups, lapsed vaccinations).
- Current process: open patient chart, check each item manually, log findings
  in a spreadsheet. Takes 20-30 minutes per patient.
- Patient 360 should let coordinators **filter patients** by care gap type
  and see who needs attention.
- Encounter history should include **wait times** if available, and flag
  any encounters where the patient left without being seen.
- Readmission alerts are important for her team too — they coordinate
  post-discharge follow-up.
- Data freshness: daily refresh is acceptable for care coordination work.
  They work on a day-ahead basis, not real-time.

### Requirements

- Patient panel view with care gap filters
- Encounter history with visit details
- Readmission alerts for post-discharge coordination
- Data freshness: 24-hour latency acceptable
- Batch review capability: 20-50 patients at once

---

## Interview 4: James Wright — Revenue Cycle Director

**Date**: January 18, 2026
**Interviewer**: Business Analyst

### Key Points

- Billing staff need quick access to a patient's **financial profile**:
  recent encounters, associated claims, payment status, outstanding balances.
- Currently takes 5-10 minutes to pull up a patient's billing history
  because the claims system and EHR are separate.
- Key calculation: **total visit cost** = encounter cost + procedure costs +
  medication costs. This should be pre-calculated and displayed per encounter.
- Claims data can be **24 hours old** — they work on a next-day basis for
  most reconciliation tasks.
- Need to see the **payer** for each claim (which insurance company) and
  the claim status (pending, approved, denied).
- Edge case: some patients have **multiple insurance payers** (primary and
  secondary). The system should show both.

### Requirements

- Financial summary per patient: encounters, claims, costs
- Total visit cost calculation (encounter + procedures + medications)
- Claim status and payer information
- Data freshness: 24-hour latency acceptable
- Support for multiple payers per patient

---

## Interview 5: Dr. Amy Nguyen — Primary Care Physician (End User)

**Date**: January 20, 2026
**Interviewer**: Business Analyst

### Key Points

- Uses patient lookup **50-100 times per day** during clinic hours.
- Most common workflow: search by patient name before each appointment
  (15-minute slots, so speed is critical).
- Needs to see **name, age, and last visit date** in search results before
  clicking into a full profile.
- When a patient has a common name (e.g., "John Smith"), there could be
  multiple matches. The system should show **date of birth** and **last 4
  of SSN** to help distinguish between patients.
- Would like a **medication list** that clearly shows what is active vs.
  what has been discontinued.
- "If I could see allergies, active meds, and last 3 encounters on one
  screen, that would save me most of the time I currently waste."

### Requirements

- Search results show: name, age, last visit date
- Duplicate handling: show DOB and SSN last 4 for disambiguation
- Medication list: active vs. discontinued distinction
- Quick-view: allergies, active meds, last 3 encounters on one screen
- Performance: instant feel — under 2 seconds
