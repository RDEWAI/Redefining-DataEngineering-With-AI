---
name: trigger-validate-ingestion
description: Routing check — natural-language prompt must invoke the validate-ingestion skill without naming it.
tags: [trigger, smoke]
max_turns: 6
timeout_seconds: 120
allowed_tools: [Read, Glob, Grep, Skill]
---

Check that every Bronze table has an ingestion config and that the retry and DQ settings in those configs match the LLD.
