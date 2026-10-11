---
name: trigger-update-ingestion
description: Routing check — natural-language prompt must invoke the update-ingestion skill without naming it.
tags: [trigger, smoke]
max_turns: 6
timeout_seconds: 120
allowed_tools: [Read, Glob, Grep, Skill]
---

Change the retry count for the claims bronze table to 5.
