---
name: trigger-validate-dag
description: Routing check — natural-language prompt must invoke the validate-dag skill without naming it.
tags: [trigger, smoke]
max_turns: 6
timeout_seconds: 120
allowed_tools: [Read, Glob, Grep, Skill]
---

Lint the hourly Airflow DAG for import errors and path conventions before I open the PR.
