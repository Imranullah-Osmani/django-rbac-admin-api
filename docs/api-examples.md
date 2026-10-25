# API Examples

These examples assume the service is running at `http://localhost:8010` and the default demo admin exists.

## 1. Issue a JWT pair

```bash
curl -s -X POST http://localhost:8010/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"ChangeMe123!"}'
```

Use the returned `access` token as a bearer token in the remaining requests.

## 2. Read the authenticated operator profile

```bash
curl -s http://localhost:8010/api/users/me/ \
  -H "Authorization: Bearer <access-token>"
```

## 3. List users within the caller's RBAC scope

```bash
curl -s http://localhost:8010/api/users/ \
  -H "Authorization: Bearer <access-token>"
```

Admins see all users. Managers see users in their organization branch, including descendant units. Manager updates must keep users in that branch: omitting `org_unit` preserves it, while explicitly setting it to `null` returns HTTP 400. Admins can clear a user's organization.

Managers cannot edit, delete, or import changes to administrator accounts. This includes Django superusers even when they have no explicit admin role assigned.

## 4. Export users to CSV

```bash
curl -s http://localhost:8010/api/users/export/ \
  -H "Authorization: Bearer <access-token>" \
  -o users-export.csv
```

The export path writes an audit log with the visible record count.

## 5. Import users from CSV

Both CSV import endpoints accept UTF-8 (with an optional BOM), preserve quoted multiline cells, and require unique non-empty headers and a consistent column count. Malformed quoting or rows return HTTP 400 before any records are written. Uploads are limited to 1 MB and 500 data rows.

```bash
curl -s -X POST http://localhost:8010/api/users/import/ \
  -H "Authorization: Bearer <access-token>" \
  -F "file=@sample-users.csv"
```

Expected CSV shape:

User imports reject the entire batch with HTTP 400 if its final role assignments would remove the last active administrator. Transferring admin access to another active or newly created account in the same upload is allowed; inactive accounts do not satisfy this requirement.

```csv
username,email,first_name,last_name,title,phone_number,org_unit_code,role_slugs
ops.manager,ops.manager@example.com,Ops,Manager,Operations Lead,+1-555-0101,OPS,manager
support.staff,support.staff@example.com,Support,Staff,Support Specialist,+1-555-0102,SUP,staff
```

Organization import/export also supports manager ownership:

Organization imports validate the final hierarchy against both uploaded rows and existing units. A parent cycle rejects the entire upload with HTTP 400 before any units are changed.

```csv
name,code,parent_code,manager_username
Support Operations,SUP,OPS,ops.manager
```

## 6. Read the organization tree

```bash
curl -s http://localhost:8010/api/org-units/tree/ \
  -H "Authorization: Bearer <access-token>"
```

This endpoint is useful for showing organization hierarchy and manager-scoped visibility in one response. For managers assigned to a child organization, their own organization is returned as the branch root.
