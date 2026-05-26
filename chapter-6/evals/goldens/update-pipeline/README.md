# update-pipeline goldens

This skill applies incremental edits — its goldens are diffs against a
known starting point, not full file contents. Phase 1 of the eval
rollout captures the **invariants** only (load-bearing strings that
must survive any edit), not full text. See
`tests/test_pipeline_skill_templates.py::TestUpdatePipelineKnowsNewFiles`.

Phase 2 will add real before/after diff goldens for:
- "add caching to lint.yml"
- "bump actions/checkout to v6 in every workflow"
- "add slack notification to deploy step"
