---
name: trigger-rca
description: Routing check — an on-call style failure description must invoke the rca skill without naming it.
tags: [trigger, smoke]
max_turns: 6
timeout_seconds: 120
allowed_tools: [Read, Glob, Grep, Skill]
---

The hourly pipeline paged us: reconciliation_bronze failed on the last run with SE_RUN_MISSING_FOR_DS=2026-10-14 in the log. Find the root cause and tell me who needs to fix what.
