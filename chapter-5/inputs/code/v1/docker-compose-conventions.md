---
Version: 1.0
Status: Approved
Topic: Local services orchestration — UC OSS + Marquez + Postgres
---

# Docker Compose Conventions

## Purpose

Every generated project runs a three-service local stack:

1. **Unity Catalog OSS server** — metastore (ports `8080`)
2. **Marquez + Marquez web** — OpenLineage backend (API `5001`, UI `3000`)
3. **Postgres 16** — Marquez's backing store (internal only)

The stack is started with `make uc-start` and stopped with `make uc-stop`.

## Pattern

- **Single root `docker-compose.yml`** — no subdirectory per service, no
  overrides file in dev.
- **Named volumes for persistence** — `unitycatalog_data`, `marquez_data`
  survive `docker compose down`. Bind mounts (`./etc/conf → /opt/...`)
  only for config files the app edits.
- **Health checks on Postgres** — `marquez` uses
  `depends_on: {marquez-db: {condition: service_healthy}}` so it only
  starts once Postgres is ready.
- **Port 5001 (not 5000) for Marquez API** — avoids the macOS AirPlay
  Receiver claiming `5000`. The container port stays `5000` (internal).
- **Pinned image tags** — use `LIBRARIES.md` versions; never rely on
  `:latest` in committed compose files.

## Illustrative snippet

```yaml
name: {project_name}

services:
  server:
    image: unitycatalog/unitycatalog:0.4.1
    ports: ["8080:8080"]
    volumes:
      - ./etc/conf:/opt/unitycatalog/etc/conf
      - unitycatalog_data:/opt/unitycatalog/etc/data

  marquez-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: marquez
      POSTGRES_DB: marquez
      POSTGRES_PASSWORD: marquez
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U marquez"]
      interval: 5s
      timeout: 5s
      retries: 10
    volumes:
      - marquez_data:/var/lib/postgresql/data

  marquez:
    image: marquezproject/marquez:0.51.1
    ports: ["5001:5000"]
    environment:
      MARQUEZ_DB_HOST: marquez-db
      MARQUEZ_DB_USER: marquez
      MARQUEZ_DB_PASSWORD: marquez
    depends_on:
      marquez-db:
        condition: service_healthy

  marquez-web:
    image: marquezproject/marquez-web:0.51.1
    ports: ["3000:3000"]
    environment:
      MARQUEZ_HOST: marquez
      MARQUEZ_PORT: "5000"
    depends_on: [marquez]

volumes:
  unitycatalog_data:
  marquez_data:
```

## Port map (keep consistent across projects)

| Port | Service | Purpose |
|---|---|---|
| 8080 | Unity Catalog server | REST API |
| 5001 | Marquez API | OpenLineage event sink |
| 3000 | Marquez web | Lineage UI |
| 5432 | Postgres | Internal only (not exposed) |

## Common pitfalls

- Exposing Postgres publicly (`"5432:5432"`) — keep it internal; Marquez
  reaches it over the compose network.
- Using `:latest` tags — irreproducible; always pin.
- Bind-mounting `data/` dirs — use named volumes so `docker compose down
  -v` cleans them explicitly.
- Forgetting the health check on `marquez-db` — Marquez race-starts and
  fails on the first `make uc-start`.

## References

- `/mvp/docker-compose.yml`
- [`LIBRARIES.md`](LIBRARIES.md) — image tags
- [`unity-catalog-pattern.md`](unity-catalog-pattern.md)
- [`openlineage-marquez-pattern.md`](openlineage-marquez-pattern.md)
