"""
Generate a second load (ds=2026-03-13) for SCD2 and fact pipeline testing.

Skips observations (4.4M rows — too large for local dev testing).

What this produces
──────────────────
Dim tables  (full snapshot, some changes → triggers SCD2 new versions):
  patients.csv      — 10% of patients "moved" to a new city
  providers.csv     — 5% of providers changed speciality
  organizations.csv — unchanged (stable reference)
  payers.csv        — unchanged (stable reference)

Fact tables  (new records only for the delta period):
  encounters.csv    — 300 new encounters
  conditions.csv    — 500 new conditions linked to new encounters
  medications.csv   — 400 new medications linked to new encounters
  allergies.csv     — 200 new allergies linked to new encounters
  claims.csv        — 300 new claims (one per new encounter)

Output:  data/raw_delta/

Usage:
    uv run python scripts/gen_delta_load.py
    uv run python run_local.py --layer all --ds 2026-03-13 --raw-path ../../data/raw_delta
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RAW = Path(__file__).parents[2] / "data" / "raw"
OUT = Path(__file__).parents[2] / "data" / "raw_delta"

random.seed(42)

OUT.mkdir(parents=True, exist_ok=True)


# ── helpers ───────────────────────────────────────────────────────────────────

def uid() -> str:
    return str(uuid.uuid4())


def rand_date(start: date = date(2026, 3, 7), days: int = 6) -> date:
    return start + timedelta(days=random.randint(0, days))


def rand_ts(start: date = date(2026, 3, 7), days: int = 6) -> str:
    d = start + timedelta(days=random.randint(0, days))
    h, m = random.randint(6, 22), random.randint(0, 59)
    return f"{d}T{h:02d}:{m:02d}:00Z"


# ── load reference data ───────────────────────────────────────────────────────

print("Loading reference data from data/raw/ ...")
# dtype=str preserves leading zeros in ZIP codes and other string-formatted numerics.
# Spark reads all fields as strings per schema; pandas must do the same to keep hashes consistent.
patients_df  = pd.read_csv(RAW / "patients.csv", dtype=str)
providers_df = pd.read_csv(RAW / "providers.csv", dtype=str)
orgs_df      = pd.read_csv(RAW / "organizations.csv", dtype=str)
payers_df    = pd.read_csv(RAW / "payers.csv", dtype=str)

patient_ids  = patients_df["Id"].tolist()
provider_ids = providers_df["Id"].tolist()
org_ids      = orgs_df["Id"].tolist()
payer_ids    = payers_df["Id"].tolist()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DIM tables — full snapshot with controlled changes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CITIES = [
    ("Austin",    "TX", "78701"),
    ("Seattle",   "WA", "98101"),
    ("Phoenix",   "AZ", "85001"),
    ("Miami",     "FL", "33101"),
    ("Portland",  "OR", "97201"),
    ("Denver",    "CO", "80201"),
    ("Nashville", "TN", "37201"),
    ("Atlanta",   "GA", "30301"),
]
STREETS = ["Elm", "Oak", "Main", "Pine", "Cedar", "Maple", "River"]

# patients: 10% change city / address / zip
p_delta = patients_df.copy()
changed = p_delta.sample(frac=0.10, random_state=42).index
for idx in changed:
    city, state, zip_ = random.choice(CITIES)
    p_delta.at[idx, "CITY"]    = city
    p_delta.at[idx, "STATE"]   = state
    p_delta.at[idx, "ZIP"]     = zip_
    p_delta.at[idx, "ADDRESS"] = f"{random.randint(100, 9999)} {random.choice(STREETS)} St"

p_delta.to_csv(OUT / "patients.csv", index=False)
print(f"  patients.csv      — {len(p_delta):,} rows | {len(changed)} changed (SCD2 new versions expected)")

# providers: 5% change speciality
SPECIALTIES = [
    "CARDIOLOGY", "NEUROLOGY", "ONCOLOGY", "PEDIATRICS",
    "ORTHOPEDICS", "DERMATOLOGY", "PSYCHIATRY", "RADIOLOGY",
]
pr_delta = providers_df.copy()
changed = pr_delta.sample(frac=0.05, random_state=42).index
for idx in changed:
    pr_delta.at[idx, "SPECIALITY"] = random.choice(SPECIALTIES)

pr_delta.to_csv(OUT / "providers.csv", index=False)
print(f"  providers.csv     — {len(pr_delta):,} rows | {len(changed)} changed (SCD2 new versions expected)")

# organizations / payers: pass through unchanged
orgs_df.to_csv(OUT / "organizations.csv", index=False)
payers_df.to_csv(OUT / "payers.csv", index=False)
print(f"  organizations.csv — {len(orgs_df):,} rows (unchanged)")
print(f"  payers.csv        — {len(payers_df):,} rows (unchanged)")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FACT tables — new records for the delta period
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ENC_TYPES = [
    ("185349003", "Encounter for check up",          "wellness"),
    ("11429006",  "Consultation",                    "outpatient"),
    ("50849002",  "Emergency room admission",        "emergency"),
    ("308646001",  "Follow-up encounter",            "outpatient"),
    ("702927004", "Encounter for tooth examination", "outpatient"),
]
COND_CODES = [
    ("44054006",  "Diabetes mellitus type 2"),
    ("59621000",  "Essential hypertension"),
    ("195662009", "Acute viral pharyngitis"),
    ("444814009", "Viral sinusitis"),
    ("40055000",  "Chronic sinusitis"),
    ("10509002",  "Acute bronchitis"),
    ("73595000",  "Stress disorder"),
]
MED_CODES = [
    ("860975",  "Metformin 500 MG Oral Tablet"),
    ("429503003", "Lisinopril 10 MG Oral Tablet"),
    ("860601",  "Atorvastatin 20 MG Oral Tablet"),
    ("834060",  "Amoxicillin 500 MG Oral Capsule"),
    ("966571",  "Omeprazole 20 MG Oral Capsule"),
]
ALLERGY_CODES = [
    ("387207008", "Ibuprofen"),
    ("372687004", "Amoxicillin"),
    ("387517004", "Paracetamol"),
    ("372687004", "Penicillin"),
]
SEVERITIES = ["MILD", "MODERATE", "SEVERE"]

# ── encounters: 300 new ───────────────────────────────────────────────────────
new_enc = []
enc_patient_map: dict[str, str] = {}  # enc_id → patient_id
enc_provider_map: dict[str, str] = {}
enc_payer_map: dict[str, str] = {}

for _ in range(300):
    eid  = uid()
    code, desc, enc_class = random.choice(ENC_TYPES)
    pat  = random.choice(patient_ids)
    prov = random.choice(provider_ids)
    org  = random.choice(org_ids)
    pay  = random.choice(payer_ids)
    base = round(random.uniform(50, 500), 2)
    start_ts = rand_ts()
    stop_ts  = rand_ts(date(2026, 3, 8), 5)

    enc_patient_map[eid]  = pat
    enc_provider_map[eid] = prov
    enc_payer_map[eid]    = pay

    new_enc.append({
        "Id": eid, "START": start_ts, "STOP": stop_ts,
        "PATIENT": pat, "ORGANIZATION": org, "PROVIDER": prov, "PAYER": pay,
        "ENCOUNTERCLASS": enc_class, "CODE": code, "DESCRIPTION": desc,
        "BASE_ENCOUNTER_COST": base,
        "TOTAL_CLAIM_COST":    round(base * random.uniform(1.5, 3.0), 2),
        "PAYER_COVERAGE":      round(base * random.uniform(0.3, 0.9), 2),
        "REASONCODE": None, "REASONDESCRIPTION": None,
    })

enc_ids = list(enc_patient_map.keys())
enc_df  = pd.DataFrame(new_enc)
enc_df.to_csv(OUT / "encounters.csv", index=False)
print(f"  encounters.csv    — {len(enc_df):,} new rows")

# ── conditions: 500 new ───────────────────────────────────────────────────────
new_cond = []
for _ in range(500):
    code, desc = random.choice(COND_CODES)
    enc   = random.choice(enc_ids)
    onset = rand_date()
    stop  = rand_date(onset, 30) if random.random() < 0.3 else None
    new_cond.append({
        "START": onset, "STOP": stop,
        "PATIENT": enc_patient_map[enc], "ENCOUNTER": enc,
        "SYSTEM": "SNOMED-CT", "CODE": code, "DESCRIPTION": desc,
    })

cond_df = pd.DataFrame(new_cond)
cond_df.to_csv(OUT / "conditions.csv", index=False)
print(f"  conditions.csv    — {len(cond_df):,} new rows")

# ── medications: 400 new ──────────────────────────────────────────────────────
new_med = []
for _ in range(400):
    code, desc = random.choice(MED_CODES)
    enc     = random.choice(enc_ids)
    start_d = rand_date()
    stop_d  = rand_date(start_d, 90) if random.random() < 0.4 else None
    base    = round(random.uniform(5, 200), 2)
    disp    = random.randint(1, 6)
    new_med.append({
        "START": start_d, "STOP": stop_d,
        "PATIENT": enc_patient_map[enc], "PAYER": enc_payer_map[enc], "ENCOUNTER": enc,
        "CODE": code, "DESCRIPTION": desc,
        "BASE_COST":       base,
        "PAYER_COVERAGE":  round(base * random.uniform(0, 0.8), 2),
        "DISPENSES":       disp,
        "TOTALCOST":       round(base * disp, 2),
        "REASONCODE": None, "REASONDESCRIPTION": None,
    })

med_df = pd.DataFrame(new_med)
med_df.to_csv(OUT / "medications.csv", index=False)
print(f"  medications.csv   — {len(med_df):,} new rows")

# ── allergies: 200 new ────────────────────────────────────────────────────────
new_allergy = []
for _ in range(200):
    code, desc = random.choice(ALLERGY_CODES)
    enc = random.choice(enc_ids)
    sev = random.choice(SEVERITIES)
    new_allergy.append({
        "START": rand_date(), "STOP": None,
        "PATIENT": enc_patient_map[enc], "ENCOUNTER": enc,
        "CODE": code, "SYSTEM": "SNOMED-CT", "DESCRIPTION": desc,
        "TYPE": "allergy", "CATEGORY": "medication",
        "REACTION1": f"Reaction to {desc}", "DESCRIPTION1": desc, "SEVERITY1": sev,
        "REACTION2": None, "DESCRIPTION2": None, "SEVERITY2": None,
    })

allergy_df = pd.DataFrame(new_allergy)
allergy_df.to_csv(OUT / "allergies.csv", index=False)
print(f"  allergies.csv     — {len(allergy_df):,} new rows")

# ── claims: one per new encounter ─────────────────────────────────────────────
new_claims = []
for row in new_enc:
    svc_date = row["START"][:10]
    new_claims.append({
        "Id":                          uid(),
        "PATIENTID":                   row["PATIENT"],
        "PROVIDERID":                  row["PROVIDER"],
        "PRIMARYPATIENTINSURANCEID":   row["PAYER"],
        "SECONDARYPATIENTINSURANCEID": None,
        "DEPARTMENTID":                uid(),
        "PATIENTDEPARTMENTID":         uid(),
        "DIAGNOSIS1": random.choice([c for c, _ in COND_CODES]),
        "DIAGNOSIS2": None, "DIAGNOSIS3": None, "DIAGNOSIS4": None,
        "DIAGNOSIS5": None, "DIAGNOSIS6": None, "DIAGNOSIS7": None, "DIAGNOSIS8": None,
        "REFERRINGPROVIDERID":  None,
        "APPOINTMENTID":        uid(),
        "CURRENTILLNESSDATE":   svc_date,
        "SERVICEDATE":          svc_date,
        "SUPERVISINGPROVIDERID": row["PROVIDER"],
        "STATUS1": "BILLED", "STATUS2": None, "STATUSP": None,
        "OUTSTANDING1":     round(random.uniform(0, 500), 2),
        "OUTSTANDING2":     None,
        "OUTSTANDINGP":     None,
        "LASTBILLEDDATE1":  svc_date,
        "LASTBILLEDDATE2":  None,
        "LASTBILLEDDATEP":  None,
        "HEALTHCARECLAIMTYPEID1": 1,
        "HEALTHCARECLAIMTYPEID2": None,
    })

claims_df = pd.DataFrame(new_claims)
claims_df.to_csv(OUT / "claims.csv", index=False)
print(f"  claims.csv        — {len(claims_df):,} new rows")

# ── skip observations ─────────────────────────────────────────────────────────
print(f"  observations.csv  — SKIPPED (4.4M rows)")

print(f"\nDone. Output: {OUT}")
print("Next step:")
print("  uv run python run_local.py --layer all --ds 2026-03-13 --raw-path ../../data/raw_delta")
