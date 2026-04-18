import csv

from django.db.models import Q
from django.http import HttpResponse
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response

from accounts.permissions import IsAdminOrManager
from audits.utils import create_audit_log

from .models import OrganizationUnit
from .serializers import OrganizationUnitSerializer


class OrganizationUnitViewSet(viewsets.ModelViewSet):
    queryset = OrganizationUnit.objects.select_related("parent", "manager").prefetch_related("children").all()
    serializer_class = OrganizationUnitSerializer
    permission_classes = [IsAdminOrManager]
    parser_classes = [MultiPartParser]
    search_fields = ("name", "code")
    ordering_fields = ("name", "code", "updated_at")

    def get_queryset(self):
        queryset = super().get_queryset()
        user = self.request.user
        if not user.is_authenticated:
            return queryset.none()
        if user.is_admin_role():
            return queryset
        if user.org_unit_id:
            return queryset.filter(Q(id=user.org_unit_id) | Q(parent_id=user.org_unit_id))
        return queryset.none()

    def perform_create(self, serializer) -> None:
        unit = serializer.save()
        create_audit_log(self.request, "created", unit, {"code": unit.code})

    def perform_update(self, serializer) -> None:
        unit = serializer.save()
        create_audit_log(self.request, "updated", unit, {"parent": unit.parent_id})

    def perform_destroy(self, instance) -> None:
        create_audit_log(self.request, "deleted", instance, {"code": instance.code})
        instance.delete()

    @action(detail=False, methods=["get"])
    def tree(self, request):
        roots = self.get_queryset().filter(parent__isnull=True)
        serializer = self.get_serializer(roots, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="export")
    def export_units(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="org-units-export.csv"'
        writer = csv.writer(response)
        writer.writerow(["name", "code", "parent_code"])
        for unit in queryset:
            writer.writerow([unit.name, unit.code, unit.parent.code if unit.parent else ""])
        create_audit_log(request, "exported", OrganizationUnit, {"record_count": queryset.count()})
        return response

    @action(detail=False, methods=["post"], url_path="import")
    def import_units(self, request):
        upload = request.FILES.get("file")
        if not upload:
            return Response({"detail": "Upload a CSV file with form field `file`."}, status=status.HTTP_400_BAD_REQUEST)

        rows = list(csv.DictReader(upload.read().decode("utf-8").splitlines()))
        processed = 0
        for row in rows:
            parent = None
            parent_code = row.get("parent_code")
            if parent_code:
                parent = OrganizationUnit.objects.filter(code=parent_code).first()
            OrganizationUnit.objects.update_or_create(
                code=row["code"].strip(),
                defaults={"name": row["name"].strip(), "parent": parent},
            )
            processed += 1

        create_audit_log(request, "imported", OrganizationUnit, {"record_count": processed})
        return Response({"processed": processed})
