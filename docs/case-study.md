# Django RBAC Admin API Case Study

## Summary

This project is a compact internal control-plane API for startups and operations-heavy teams. The goal is to provide one place to manage users, role-based access, organization structure, and auditable operational changes without building a full enterprise platform.

The implementation in this repository is intentionally small, but the delivery pattern is the same one used in real internal-tool work: secure authentication, scoped access, traceable change history, and simple bulk data workflows for operational teams.

## The problem

Startups often reach the same point at roughly the same time:

- more than one team needs to manage internal users
- access rules can no longer live in ad hoc code branches or spreadsheet notes
- someone needs to answer "who changed this, and when?"
- operations staff need import/export workflows because not every change happens one record at a time

At that stage, a basic CRUD admin panel stops being enough. The system needs structure, security, and clear operator boundaries.

## The objective

Build a lightweight internal admin service that can handle:

- JWT-secured API access for integrations and internal clients
- fixed system roles with predictable authority boundaries
- organization-aware user management
- permission visibility for admin operators
- audit logs for sensitive changes
- CSV import/export for back-office workflows
- Dockerized deployment for fast setup in review, staging, or demos

## Solution design

### 1. Fixed RBAC model

The API uses three system roles:

- `admin`
- `manager`
- `staff`

This keeps the access model clear for reviewers and realistic for small teams. Instead of exposing an open-ended role model too early, the system demonstrates a controlled baseline:

- admins manage the full system
- managers operate within their own organization scope
- staff can authenticate and access their own limited resources

### 2. Organization-aware scoping

Role checks alone are not enough for real internal systems. A manager should not automatically have cross-company access just because they are a manager.

This project adds organization-unit scoping so management access is tied to where the user sits in the hierarchy. That is the design detail that makes the system feel operational rather than academic.

### 3. Auditability as a first-class behavior

User changes, role updates, imports, exports, and organization edits generate audit events. That matters because internal systems are usually judged by trust and traceability, not just by whether a form submits successfully.

The audit trail makes the service easier to defend in demos and more credible for startup/internal-tool work.

### 4. Import/export for real admin work

Operations teams regularly need to:

- onboard users in batches
- update department structure from spreadsheets
- export records for review or reconciliation

That is why CSV import/export is part of the design instead of being treated as a "future enhancement." It makes the repo look closer to paid internal-tool work.

### 5. Browser and API access together

The repository exposes both:

- Django admin for operator-facing workflows
- protected API endpoints for programmatic access

That combination is valuable in portfolio terms because it shows both implementation styles:

- direct operator tooling
- backend platform/API thinking

## Key implementation choices

### JWT instead of session-only auth

JWT support gives the project a stronger backend profile. It demonstrates that the service can support internal clients, automation, or frontend consumers without being limited to server-rendered session workflows.

### PostgreSQL in Docker

The Docker setup uses PostgreSQL by default so the demo environment reflects a more realistic deployment posture. SQLite remains useful for lightweight local work, but PostgreSQL is the stronger portfolio signal.

### Permission catalog + fixed roles

The system exposes permission data while keeping the role model intentionally constrained. That balance is deliberate:

- enough flexibility to look like a real internal system
- enough discipline to avoid the messier "custom everything" shape that often appears in rushed internal tools

## Result

The finished project presents well for the kinds of clients who need:

- startup admin backends
- internal operations tooling
- staff and org management
- compliance-friendly change tracking
- pragmatic import/export features

It is especially effective as a portfolio piece because it communicates senior-engineer instincts:

- access is scoped, not assumed
- auditability is built in, not postponed
- deployment is considered early
- internal-user workflows are treated as product requirements

## Why this attracts clients

This project signals that the developer can do more than build public CRUD APIs. It shows the ability to design internal systems where correctness, permissions, traceability, and operator usability matter.

That makes it relevant to:

- startup founders building first-generation internal tools
- small platforms needing admin backends
- operations teams replacing manual spreadsheets
- companies that need controlled internal APIs without enterprise overhead

## Next production steps

If this were being taken from strong portfolio demo to production handoff, the next steps would be:

1. add committed migrations and release workflow discipline
2. add SSO or identity-provider integration
3. introduce object-level policy rules where required
4. add background jobs for large imports and export delivery
5. add environment-specific observability and alerting

## Closing note

This repository is intentionally compact, but the case-study value comes from the design choices behind it. The point is not that it is large. The point is that it solves the right internal problems in the right order, which is exactly what clients look for in startup and operational backend work.
