# Security Policy

This repository is a portfolio-grade internal admin API. It is not deployed as a public production service, but it is maintained with the same security posture expected for client-facing backend work.

## Supported Scope

Security review applies to the current `main` branch.

Covered areas:

- JWT authentication and token refresh behavior
- Role-based access control for `admin`, `manager`, and `staff`
- Organization-scoped user visibility
- CSV import/export authorization boundaries
- Audit-log integrity for operational changes
- Docker and dependency update hygiene

## Reporting

Please report suspected vulnerabilities privately through GitHub's vulnerability reporting tools when available. If private reporting is unavailable, open a minimal issue that describes the affected area without posting exploit details, credentials, tokens, or private data.

Useful report details:

- affected endpoint or workflow
- expected authorization behavior
- observed behavior
- reproduction steps using local demo data
- impact and suggested severity

## Local Security Checks

Run the verification script before opening a pull request:

```powershell
.\scripts\verify.ps1
```

The script validates Docker Compose configuration, Django system checks, migration drift, and the RBAC test suite.

## Hardening Notes

- Never commit `.env`, local databases, logs, or generated secrets.
- Rotate `SECRET_KEY` and admin credentials for any real deployment.
- Replace demo passwords before exposing the service outside local development.
- Keep Dependabot alerts and GitHub Actions failures visible and triaged.
- Review audit logs around bulk import/export workflows because those paths can change many records quickly.
