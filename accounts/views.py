import csv

from django.contrib.auth.models import Permission
from django.db import transaction
from django.http import HttpResponse
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from audits.utils import create_audit_log
from organizations.models import OrganizationUnit

from .models import Role, User
from .permissions import IsAdminOrManager, IsAdminRole
from .serializers import PermissionSerializer, RoleSerializer, UserSerializer


class PermissionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = Permission.objects.select_related("content_type").order_by("content_type__app_label", "codename")
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminRole]


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.prefetch_related("permissions").all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminRole]
    http_method_names = ["get", "put", "patch", "head", "options"]
    search_fields = ("name", "slug")
    ordering_fields = ("name", "updated_at")

    def get_queryset(self):
        return super().get_queryset().filter(slug__in=["admin", "manager", "staff"])

    def perform_update(self, serializer) -> None:
        role = serializer.save()
        create_audit_log(
            self.request,
            "updated",
            role,
            {"permissions": list(role.permissions.values_list("codename", flat=True))},
        )


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("org_unit").prefetch_related("roles__permissions").all()
    serializer_class = UserSerializer
    permission_classes = [IsAdminOrManager]
    parser_classes = [MultiPartParser]
    search_fields = ("username", "email", "first_name", "last_name")
    ordering_fields = ("username", "email", "date_joined")

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        if user.is_admin_role():
            return queryset
        if user.org_unit_id:
            return queryset.filter(org_unit_id=user.org_unit_id)
        return queryset.filter(id=user.id)

    def perform_create(self, serializer) -> None:
        user = serializer.save()
        user.set_unusable_password()
        user.save(update_fields=["password"])
        create_audit_log(self.request, "created", user, {"username": user.username, "email": user.email})

    def perform_update(self, serializer) -> None:
        user = serializer.save()
        create_audit_log(self.request, "updated", user, {"roles": user.role_slugs})

    def perform_destroy(self, instance) -> None:
        create_audit_log(self.request, "deleted", instance, {"username": instance.username})
        instance.delete()

    @action(detail=False, methods=["get"], url_path="export")
    def export_users(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="users-export.csv"'
        writer = csv.writer(response)
        writer.writerow(["username", "email", "first_name", "last_name", "title", "org_unit_code", "role_slugs"])
        for user in queryset:
            writer.writerow(
                [
                    user.username,
                    user.email,
                    user.first_name,
                    user.last_name,
                    user.title,
                    user.org_unit.code if user.org_unit else "",
                    ",".join(user.role_slugs),
                ]
            )
        create_audit_log(request, "exported", User, {"record_count": queryset.count()})
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_users(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "Upload a CSV file with form field `file`."}, status=status.HTTP_400_BAD_REQUEST)

        reader = csv.DictReader(upload.read().decode("utf-8").splitlines())
        missing_headers = {"username", "email"} - set(reader.fieldnames or [])
        if missing_headers:
            return Response(
                {"detail": f"Missing required CSV columns: {', '.join(sorted(missing_headers))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = list(reader)
        errors, prepared_rows = self._prepare_user_import_rows(rows)
        if errors:
            return Response({"processed": 0, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        processed = 0
        with transaction.atomic():
            for prepared in prepared_rows:
                user, _ = User.objects.update_or_create(
                    email=prepared["email"],
                    defaults={
                        "username": prepared["username"],
                        "first_name": prepared["first_name"],
                        "last_name": prepared["last_name"],
                        "title": prepared["title"],
                        "org_unit": prepared["org_unit"],
                    },
                )
                user.roles.set(prepared["roles"])
                processed += 1

        create_audit_log(request, "imported", User, {"record_count": processed})
        return Response({"processed": processed, "errors": []})

    def _prepare_user_import_rows(self, rows):
        errors = []
        prepared_rows = []
        operator = self.request.user
        manager_mode = not operator.is_admin_role()

        for row_number, row in enumerate(rows, start=2):
            username = (row.get("username") or "").strip()
            email = (row.get("email") or "").strip()
            org_code = (row.get("org_unit_code") or "").strip()
            role_slugs = [slug.strip() for slug in (row.get("role_slugs") or "").split(",") if slug.strip()]

            if not username:
                errors.append({"row": row_number, "field": "username", "detail": "Username is required."})
            if not email:
                errors.append({"row": row_number, "field": "email", "detail": "Email is required."})

            org_unit = None
            if org_code:
                org_unit = OrganizationUnit.objects.filter(code=org_code).first()
                if not org_unit:
                    errors.append({"row": row_number, "field": "org_unit_code", "detail": f"Unknown organization unit `{org_code}`."})

            roles = list(Role.objects.filter(slug__in=role_slugs))
            found_role_slugs = {role.slug for role in roles}
            missing_role_slugs = sorted(set(role_slugs) - found_role_slugs)
            if missing_role_slugs:
                errors.append({"row": row_number, "field": "role_slugs", "detail": f"Unknown roles: {', '.join(missing_role_slugs)}."})

            if manager_mode:
                if "admin" in role_slugs:
                    errors.append({"row": row_number, "field": "role_slugs", "detail": "Managers cannot import admin users."})
                if not operator.org_unit_id:
                    errors.append({"row": row_number, "field": "org_unit_code", "detail": "Manager must belong to an organization unit."})
                elif not org_unit or org_unit.id != operator.org_unit_id:
                    errors.append({"row": row_number, "field": "org_unit_code", "detail": "Managers can only import users into their own organization unit."})

            prepared_rows.append(
                {
                    "username": username,
                    "email": email,
                    "first_name": (row.get("first_name") or "").strip(),
                    "last_name": (row.get("last_name") or "").strip(),
                    "title": (row.get("title") or "").strip(),
                    "org_unit": org_unit,
                    "roles": roles,
                }
            )

        return errors, prepared_rows

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
