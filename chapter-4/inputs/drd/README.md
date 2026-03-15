# DRD Input Documents

Place input documents in this directory for the BA Agent to process. Organize by project:

```
inputs/drd/
├── samples/                    # Reference samples (Patient 360)
│   ├── business_request.md     # Business need and objectives
│   ├── stakeholder_notes.md    # Interview transcripts and notes
│   ├── source_system_docs.md   # Source system documentation
│   └── data_catalog.md         # Existing data catalog entries
└── {your-project}/             # Your project inputs
    ├── business_request.md
    ├── stakeholder_notes.md
    ├── source_system_docs.md
    └── data_catalog.md
```

## Input Types

| Document | Purpose | What to Include |
|----------|---------|-----------------|
| Business Request | The "why" | Business problem, objectives, success metrics, target users |
| Stakeholder Notes | The "who needs what" | Interview summaries, per-stakeholder requirements, priorities |
| Source System Docs | The "where from" | System names, table schemas, access methods, data volumes |
| Data Catalog | The "what exists" | Already-cataloged datasets, column lists, row counts |

## Usage

To generate a DRD from these inputs, use the `/create-drd` skill:

```
/create-drd chapter-4/inputs/drd/samples
```
