# Healthcare Analytics Pipeline - OpenHands Test

## Business Context
We need to build a healthcare analytics pipeline using the Synthea patient data.
This will demonstrate the OpenHands SDK integration where agents can
load, transform, and query the data.

## Objectives
- Analyze patient demographics and encounters
- Create a medallion architecture (bronze, silver, gold)
- Implement data quality rules
- Generate implementation stories

## Data Sources

### Source Type Configuration
```
type: csv
directory: data/raw/
```

**Note**: Raw CSV files from Synthea healthcare data generator.

### Available Tables/Files
- `patients` - Patient demographics
- `encounters` - Patient encounters
- `conditions` - Medical conditions
- `medications` - Prescribed medications
- `observations` - Clinical observations
- `allergies` - Patient allergies
- `careplans` - Care plans
- `claims` - Insurance claims
- `claims_transactions` - Claim transactions
- `devices` - Medical devices
- `imaging_studies` - Imaging studies
- `immunizations` - Immunization records
- `organizations` - Healthcare organizations
- `payers` - Insurance payers
- `payer_transitions` - Payer transition history
- `procedures` - Medical procedures
- `providers` - Healthcare providers
- `supplies` - Medical supplies

## Expected Outcomes
- Patient 360 view combining demographics and encounters (silver/gold layer)
- Condition prevalence metrics
- Encounter trends by month
- Data quality dashboards
