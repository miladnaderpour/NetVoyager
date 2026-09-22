# Architecture

## Execution

- The Vue app and independently installed CLI call the FastAPI service.
- The API persists job requests and enqueues work through the broker.
- Celery workers run discovery, import, and NetBox comparison tasks.
- One Celery Beat process invokes a dispatcher for stored recurring schedules.
- PostgreSQL stores schedules, jobs, run history, and reviewed observations.
- A separate broker transports tasks; it is not the system of record.

## Dependency boundaries

`apps/cli` depends only on HTTP client and CLI libraries. It does not import `packages/` or server app code. The API and workers can depend on server-side packages. All external observations are retained separately from approved inventory changes.

## Planned safeguards

Define scan scope before launch; avoid overlapping active runs per site and task type. Keep retries idempotent. Review diffs before NetBox writes, and record the evidence and job that produced each proposed change.
