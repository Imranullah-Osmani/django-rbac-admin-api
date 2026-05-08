# Contributing

This repository is maintained as a compact internal-admin API portfolio project. Contributions should keep the system easy to review, easy to run, and clearly connected to real back-office use cases.

## Local Setup

```powershell
copy .env.example .env
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo_workspace
```

Docker users can run:

```powershell
docker compose up --build
```

## Verification

Run the full local verification script before opening a pull request:

```powershell
.\scripts\verify.ps1
```

The script checks Docker Compose configuration, Django system checks, migration drift, and the RBAC/org-scope test suite.

## Change Guidelines

- Keep the fixed system roles limited to `admin`, `manager`, and `staff`.
- Preserve manager scoping rules for user and organization endpoints.
- Add or update tests when changing authentication, RBAC, CSV import/export, audit logs, or organization hierarchy behavior.
- Keep demo data deterministic so reviewers can reproduce walkthroughs quickly.
- Do not commit local `.env` files, databases, logs, generated secrets, or media artifacts.

## Pull Request Checklist

- The README or docs are updated when setup, endpoints, or workflows change.
- `.\scripts\verify.ps1` passes locally.
- New behavior has focused regression coverage.
- Security-sensitive changes are checked against [SECURITY.md](SECURITY.md).
