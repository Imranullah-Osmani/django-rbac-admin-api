import csv

from django.contrib.auth.models import Permission
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
        processed = 0
        for row in reader:
            org_unit = None
            org_code = row.get("org_unit_code")
            if org_code:
                org_unit = OrganizationUnit.objects.filter(code=org_code).first()

            user, _ = User.objects.update_or_create(
                email=row["email"].strip(),
                defaults={
                    "username": row["username"].strip(),
                    "first_name": row.get("first_name", "").strip(),
                    "last_name": row.get("last_name", "").strip(),
                    "title": row.get("title", "").strip(),
                    "org_unit": org_unit,
                },
            )
            role_slugs = [slug.strip() for slug in row.get("role_slugs", "").split(",") if slug.strip()]
            user.roles.set(Role.objects.filter(slug__in=role_slugs))
            processed += 1

        create_audit_log(request, "imported", User, {"record_count": processed})
        return Response({"processed": processed})

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated], url_path="me")
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
