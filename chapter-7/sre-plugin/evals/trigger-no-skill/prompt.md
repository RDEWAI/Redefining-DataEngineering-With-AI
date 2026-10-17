---
name: trigger-no-skill
description: Negative routing check — an unrelated request must not invoke the rca skill.
tags: [trigger, smoke]
max_turns: 4
timeout_seconds: 90
allowed_tools: [Read, Glob, Grep, Skill]
---

Write a Python one-liner that reverses a string. Just the code, no explanation.
