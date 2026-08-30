"""AI workflows over the Patient 360 Gold layer (the "AI Workflows" block of the architecture).

Forward-deployed workflows that sit at the Serve edge: a cheap deterministic step detects a
candidate, an AI step reasons over the knowledge base (semantic + ontology + taxonomy + data
contracts) to make a judgment a fixed rule can't, and the result is routed out as an action
with a feedback record that closes the loop.

Current workflow:
  cost_triage — Cost Anomaly Triage Agent (:mod:`ai_workflows.cost_triage`).
"""

from __future__ import annotations
