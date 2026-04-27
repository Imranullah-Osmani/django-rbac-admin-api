# Monitoring Notes

This service exposes health endpoints and Docker health checks so the demo behaves like a real internal API instead of a bare development server.

## Health endpoints

- `/health/live/` confirms the Django process is responding.
- `/health/ready/` confirms the API can open a database connection.

## Docker health checks

Docker Compose checks:

- the PostgreSQL container with `pg_isready`
- the API container through `/health/ready/`

This gives a reviewer a quick way to see whether the control plane is actually ready, not just whether a process started.

## Production additions

- structured request logging with request ids
- metrics for auth failures, user writes, imports, exports, and audit log volume
- alerting on readiness failures and elevated 5xx responses
- background-job tracking for larger CSV imports
