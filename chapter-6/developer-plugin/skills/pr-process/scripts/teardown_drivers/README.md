# Teardown Drivers — Contract

The `pr-process` skill destroys a developer sandbox on PR approval by
invoking a **teardown driver**. Drivers are pluggable so the same skill
can be used in different teaching scenarios (local docker, sandboxed
cloud, etc.) without rewrites.

Chapter-6 ships one driver:

| Driver | Script | Applies when |
|---|---|---|
| `local-docker` | `local_docker.sh` | `{project_root}/_infra/docker/docker-compose.yml` exists |

To extend this set, add a sibling script in this directory and register
it in `inputs/code/v1/teardown-pattern.md` under "Driver Registry".

## Contract

A driver is a single executable script (shell or Python). It exposes
three modes via the **first positional argument**:

### `--check`

Print a JSON summary of what *would* be destroyed. **Do not destroy
anything.** Exit 0.

The JSON is what the PR-body template consumes to populate the
"Sandbox Teardown on Approval" block, so reviewers can see the plan
before approving.

```json
{
  "driver": "<name>",
  "started_at": "<ISO-8601 UTC>",
  "project_root": "<path>",
  "destroyed": [
    {"kind": "container", "name": "..."},
    {"kind": "volume", "name": "..."},
    {"kind": "network", "name": "..."}
  ],
  "skipped": []
}
```

### `--dry-run`

Print the exact shell commands the driver would execute if invoked with
`--destroy`. One command per line. Exit 0.

This is what the skill displays to the user before invoking destroy, so
the human can spot accidents (e.g. `docker system prune`) without
needing to read the driver source.

### `--destroy`

Actually destroy. On success: print the JSON summary above plus
`duration_s` and exit 0. On failure: print a `{"driver": "...",
"error": "..."}` body on stderr and exit non-zero.

The driver MUST scope its destroy operations:
- For docker drivers: use `-f <compose-file>` and label filters; never
  `docker system prune` or unfiltered `docker volume prune`.
- For cloud drivers: target only resources tagged with the sandbox's
  ID; never delete by name pattern alone.

## Driver registration

Drivers register themselves in `inputs/code/v1/teardown-pattern.md`
under the **Driver Registry** section:

```yaml
- name: local-docker
  script_path: developer-plugin/skills/pr-process/scripts/teardown_drivers/local_docker.sh
  applies_when: "{project_root}/_infra/docker/docker-compose.yml"
  description: Tears down the patient_360 docker-compose stack (UC OSS, Marquez, Postgres, Airflow, OTel).
```

The `pr-process` skill reads this registry and picks the first driver
whose `applies_when` resolves to an existing path. If multiple drivers
match, it asks the user. If none match, it stops without running any
destructive op.

## Adding a new driver — checklist

1. Add `<name>.sh` (or `<name>.py`) to this directory.
2. Implement `--check`, `--dry-run`, `--destroy`.
3. Make it executable: `chmod +x <name>.sh`.
4. Register in `inputs/code/v1/teardown-pattern.md`.
5. Add an end-to-end eval scenario under
   `chapter-6/evals/skill-creator/pr-process.eval.md`.

## Reference

- Skill: [`../../SKILL.md`](../../SKILL.md) — Phase 4 invokes the driver.
- Pattern: `inputs/code/v1/teardown-pattern.md` — registry + extension
  guide.
- CI side: `_infra/ci/.github/workflows/sandbox-cleanup.yml` — calls the
  same driver from GitHub Actions on PR close.
