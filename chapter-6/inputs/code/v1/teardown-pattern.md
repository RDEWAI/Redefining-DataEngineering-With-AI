---
Version: 1.0
Status: Approved
Topic: Sandbox teardown drivers — pluggable contract for pr-process
---

# Teardown Pattern — Pluggable Sandbox Destruction

## Purpose

In real data-engineering projects the developer sandbox used to build a
story is **destroyed** once the PR is approved/merged. This keeps cost
and orphaned state from accumulating across stories. The sandbox can be:

- **Local**: a `docker-compose` stack on the engineer's laptop (UC OSS,
  Marquez, Postgres, Airflow). This is what chapter-6 ships.
- **Sandboxed cloud**: an ephemeral Databricks workspace + UC catalog,
  an EKS preview namespace, a GCP scratch project, etc.

The [`pr-process`](../../developer-plugin/skills/pr-process/SKILL.md)
skill is **driver-agnostic**: it picks a teardown driver from this
pattern's registry based on what the current workspace contains, then
invokes the driver's `--check` / `--dry-run` / `--destroy` modes.

Adding a new driver does not require editing the `pr-process` skill —
only this pattern doc + a new script under
`developer-plugin/skills/pr-process/scripts/teardown_drivers/`.

## Pattern

- **One driver per sandbox shape.** A driver knows exactly one thing:
  how to destroy the resources of one kind of sandbox.
- **Driver = single executable script** (shell or Python). The contract
  is the three-mode interface (`--check`, `--dry-run`, `--destroy`),
  not a Python class hierarchy — drivers can be implemented in any
  language.
- **Scoped destruction only.** Drivers MUST target only the sandbox
  they own: `-f docker-compose.yml` + label filters for docker;
  resource tags / workspace IDs for cloud. No `docker system prune`,
  no `aws s3 rm s3://bucket --recursive` against an unscoped bucket.
- **JSON summary out, JSON error out.** Drivers print a stable JSON
  schema so the PR-body template, the `sandbox-cleanup.yml` workflow,
  and any future audit tooling can all parse the same thing.
- **Idempotent.** Calling `--destroy` twice is safe (no resources →
  empty summary, exit 0).
- **Discovery beats configuration.** The driver finds its own targets
  by reading the compose file / cloud tags. The skill passes no list
  of resources to destroy.

## Driver Contract

Every driver MUST implement three modes via positional arg 1:

| Mode | Purpose | Output | Exit |
|---|---|---|---|
| `--check` | What *would* be destroyed | JSON summary | 0 |
| `--dry-run` | Exact shell commands | One per line | 0 |
| `--destroy` | Actually destroy | JSON summary + duration | 0 (success), non-zero (failure) |

### JSON summary schema

```json
{
  "driver": "<name>",
  "started_at": "<ISO-8601 UTC>",
  "project_root": "<path or workspace id>",
  "duration_s": <number, only on --destroy>,
  "destroyed": [
    {"kind": "container",    "name": "patient_360-uc"},
    {"kind": "volume",       "name": "patient_360_uc-data"},
    {"kind": "network",      "name": "patient_360_default"},
    {"kind": "directory",    "name": "/path/to/uc-source"},
    {"kind": "uc-schema",    "name": "ephem_user42_silver"},
    {"kind": "databricks-job","name": "1234"}
  ],
  "skipped": [
    {"kind": "<kind>", "name": "<name>", "reason": "<reason>"}
  ]
}
```

### Error envelope (non-zero exit)

```json
{
  "driver": "<name>",
  "error": "<short>",
  "detail": "<verbose, includes stderr>"
}
```

Printed on stderr, not stdout, so the calling skill can distinguish.

## Driver Registry

The `pr-process` skill reads this section as YAML. The first entry whose
`applies_when` resolves to an existing path / matches the current
workspace is selected. If multiple match, the skill asks the user.

```yaml
- name: local-docker
  script_path: developer-plugin/skills/pr-process/scripts/teardown_drivers/local_docker.sh
  applies_when: "{project_root}/_infra/docker/docker-compose.yml"
  description: |
    Tears down the patient_360 docker-compose stack: UC OSS, Marquez,
    Postgres, Airflow, OTel collector. Removes named volumes
    (uc-data, marquez-db) and the project network. Optionally removes
    the uc-ui-source clone if a .uc-ui-source marker is present.
```

### Extension example — `cloud-databricks` (not shipped)

A reader following chapter-6 in their own cloud project would add an
entry like this and a sibling script. The `pr-process` skill picks it
up automatically once the file paths match.

```yaml
# NOT SHIPPED — illustrative only. Show readers the extension path.
- name: cloud-databricks
  script_path: developer-plugin/skills/pr-process/scripts/teardown_drivers/cloud_databricks.py
  applies_when: "{workspace_root}/sandbox.databricks.json"
  description: |
    Destroys the ephemeral Databricks sandbox: deletes UC schemas
    matching the workspace's sandbox tag, deletes the Databricks job
    cluster, and revokes the workspace access token.
```

The hypothetical `cloud_databricks.py` would, in `--destroy`:

1. Read `sandbox.databricks.json` for `workspace_url`, `sandbox_tag`,
   `pat_secret_name`.
2. Call `POST /api/2.1/unity-catalog/schemas/<schema>?force=true` for
   every schema tagged `sandbox_tag=<tag>`.
3. Call `POST /api/2.1/jobs/delete` for every job tagged the same.
4. Call `DELETE /api/2.0/token-management/tokens/<token_id>` to
   revoke the PAT.
5. Emit the JSON summary with one `destroyed` entry per resource.

The same `pr-process` skill drives both drivers — the only thing that
changes is which script gets invoked. That's the teaching takeaway.

### Extension example — `cloud-eks` (not shipped)

```yaml
# NOT SHIPPED — illustrative only.
- name: cloud-eks
  script_path: developer-plugin/skills/pr-process/scripts/teardown_drivers/cloud_eks.sh
  applies_when: "{workspace_root}/sandbox.eks.yaml"
  description: |
    Deletes the EKS preview namespace and its Helm releases. Scoped
    by sandbox label so no shared cluster resources are touched.
```

## Common pitfalls

- **`docker system prune` in a driver.** Nukes unrelated containers on
  the user's machine. Always use `docker compose -f <file> down -v`
  + label-filtered `volume prune`.
- **Driver hardcodes the compose file path.** Use workspace discovery
  or `PATIENT360_PROJECT_ROOT`; the driver script in this repo walks
  up from `$PWD` looking for `_infra/docker/docker-compose.yml`.
- **Driver fails silently.** Always exit non-zero on failure with a
  JSON error envelope on stderr. A partial teardown reported as
  success is worse than no teardown.
- **`--check` runs the destructive op.** `--check` is read-only. Many
  drivers cheat and use docker daemon lookups in `--check` — that's
  fine, but anything that mutates state must wait for `--destroy`.
- **JSON summary uses unstable keys.** The schema above is the
  contract. Adding optional fields is OK; renaming existing ones
  breaks the PR-body template and `sandbox-cleanup.yml`.

## Where this pattern is consumed

1. [`pr-process` skill, Phase 4](../../developer-plugin/skills/pr-process/SKILL.md)
   — picks a driver, runs `--check`/`--dry-run`/`--destroy`.
2. PR body template
   ([`pr_body.md.j2`](../../developer-plugin/skills/pr-process/pr_body.md.j2))
   — renders the "Sandbox Teardown on Approval" block from `--check`
   JSON.
3. `sandbox-cleanup.yml` workflow (generated by `create-pipeline`) —
   calls the same driver from GitHub Actions when a PR is closed, so
   teardown happens even if the developer never ran `pr-process`
   locally.
4. [Driver README](../../developer-plugin/skills/pr-process/scripts/teardown_drivers/README.md)
   — restates the contract next to the drivers themselves.

## References

- [`docker-compose-conventions.md`](docker-compose-conventions.md) —
  named volumes the `local-docker` driver removes.
- [`ci-cd-pattern.md`](ci-cd-pattern.md) — `sandbox-cleanup.yml`
  consumes the same driver.
- [`unity-catalog-pattern.md`](unity-catalog-pattern.md) — UC schemas
  the hypothetical cloud driver would clean up.
