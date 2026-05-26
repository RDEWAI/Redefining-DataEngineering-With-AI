# validate-pipeline goldens

This skill has no executable validator script yet (see SKILL.md — the
validation runs as prose in a Claude session). Its goldens are
**phrasing checks** on the SKILL.md itself: the CRITICAL checks list
must enumerate the three new workflow filenames and the three
load-bearing strings (`if: always()`, `teardown_drivers`,
`environment: production`). Those checks are covered by
`tests/test_pipeline_skill_templates.py::TestValidatePipelineCheckCoverage`.

Phase 2 (or 3) plans to add `validate-pipeline/scripts/validate_pipeline.py`
which would emit a real validator report; full text goldens become
viable at that point.
