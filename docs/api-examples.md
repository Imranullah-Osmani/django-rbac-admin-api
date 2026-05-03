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

Admins see all users. Managers see only users in their own organization unit.

## 4. Export users to CSV

```bash
curl -s http://localhost:8010/api/users/export/ \
  -H "Authorization: Bearer <access-token>" \
  -o users-export.csv
```

The export path writes an audit log with the visible record count.

## 5. Import users from CSV

```bash
curl -s -X POST http://localhost:8010/api/users/import/ \
  -H "Authorization: Bearer <access-token>" \
  -F "file=@sample-users.csv"
```

Expected CSV shape:

```csv
username,email,first_name,last_name,title,org_unit_code,role_slugs
ops.manager,ops.manager@example.com,Ops,Manager,Operations Lead,OPS,manager
support.staff,support.staff@example.com,Support,Staff,Support Specialist,SUP,staff
```

## 6. Read the organization tree

```bash
curl -s http://localhost:8010/api/org-units/tree/ \
  -H "Authorization: Bearer <access-token>"
```

This endpoint is useful for showing organization hierarchy and manager-scoped visibility in one response.
