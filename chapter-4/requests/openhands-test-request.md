# Healthcare Analytics Pipeline - OpenHands Test

## Business Context
We need to build a healthcare analytics pipeline using the Synthea patient data
already loaded in DuckDB. This will demonstrate the OpenHands SDK integration
where agents can query the database directly.

## Objectives
- Analyze patient demographics and encounters
- Create a medallion architecture (bronze, silver, gold)
- Implement data quality rules
- Generate implementation stories

## Data Sources
The data is already loaded in DuckDB at `../data/duckdb/raw.db`:
- `synthea.patients` - Patient demographics
- `synthea.encounters` - Patient encounters
- `synthea.conditions` - Medical conditions
- `synthea.medications` - Prescribed medications
- `synthea.observations` - Clinical observations

## Expected Outcomes
- Patient 360 view combining demographics and encounters
- Condition prevalence metrics
- Encounter trends by month
- Data quality dashboards
