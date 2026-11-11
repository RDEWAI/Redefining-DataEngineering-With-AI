---
name: trigger-complete-stories
description: Routing check — natural-language prompt must invoke the complete-stories skill without naming it.
tags: [trigger, smoke]
max_turns: 6
timeout_seconds: 120
allowed_tools: [Read, Glob, Grep, Skill]
---

Are we done with EPIC-02 yet? Close it out if so.
