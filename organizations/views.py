import csv

from django.db import transaction
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

        reader = csv.DictReader(upload.read().decode("utf-8").splitlines())
        missing_headers = {"name", "code"} - set(reader.fieldnames or [])
        if missing_headers:
            return Response(
                {"detail": f"Missing required CSV columns: {', '.join(sorted(missing_headers))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        rows = list(reader)
        errors, prepared_rows = self._prepare_org_import_rows(rows)
        if errors:
            return Response({"processed": 0, "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        processed = 0
        with transaction.atomic():
            for prepared in prepared_rows:
                unit, _ = OrganizationUnit.objects.update_or_create(
                    code=prepared["code"],
                    defaults={"name": prepared["name"], "parent": None},
                )
                prepared["unit"] = unit
                processed += 1

            unit_by_code = {prepared["code"]: prepared["unit"] for prepared in prepared_rows}
            unit_by_code.update({unit.code: unit for unit in OrganizationUnit.objects.all()})
            for prepared in prepared_rows:
                parent_code = prepared["parent_code"]
                parent = unit_by_code.get(parent_code) if parent_code else None
                if prepared["unit"].parent_id != getattr(parent, "id", None):
                    prepared["unit"].parent = parent
                    prepared["unit"].save(update_fields=["parent", "updated_at"])

        create_audit_log(request, "imported", OrganizationUnit, {"record_count": processed})
        return Response({"processed": processed, "errors": []})

    def _prepare_org_import_rows(self, rows):
        errors = []
        prepared_rows = []
        existing_units = {unit.code: unit for unit in OrganizationUnit.objects.all()}
        incoming_codes = {(row.get("code") or "").strip() for row in rows if (row.get("code") or "").strip()}

        for row_number, row in enumerate(rows, start=2):
            name = (row.get("name") or "").strip()
            code = (row.get("code") or "").strip()
            parent_code = (row.get("parent_code") or "").strip()

            if not name:
                errors.append({"row": row_number, "field": "name", "detail": "Name is required."})
            if not code:
                errors.append({"row": row_number, "field": "code", "detail": "Code is required."})
            if code and parent_code == code:
                errors.append({"row": row_number, "field": "parent_code", "detail": "An organization unit cannot be its own parent."})
            if parent_code and parent_code not in existing_units and parent_code not in incoming_codes:
                errors.append({"row": row_number, "field": "parent_code", "detail": f"Unknown parent organization unit `{parent_code}`."})

            prepared_rows.append({"name": name, "code": code, "parent_code": parent_code})

        parent_by_code = {row["code"]: row["parent_code"] for row in prepared_rows if row["code"]}
        for row_number, prepared in enumerate(prepared_rows, start=2):
            code = prepared["code"]
            seen = set()
            parent_code = prepared["parent_code"]
            while parent_code:
                if parent_code == code or parent_code in seen:
                    errors.append({"row": row_number, "field": "parent_code", "detail": "Organization import would create a parent cycle."})
                    break
                seen.add(parent_code)
                parent_code = parent_by_code.get(parent_code)

        return errors, prepared_rows
