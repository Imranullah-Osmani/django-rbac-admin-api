from rest_framework import serializers

from .models import OrganizationUnit


class OrganizationUnitSerializer(serializers.ModelSerializer):
    parent_name = serializers.CharField(source="parent.name", read_only=True)
    manager_name = serializers.SerializerMethodField()
    children = serializers.SerializerMethodField()

    class Meta:
        model = OrganizationUnit
        fields = (
            "id",
            "name",
            "code",
            "parent",
            "parent_name",
            "manager",
            "manager_name",
            "metadata",
            "children",
            "created_at",
            "updated_at",
        )

    def get_children(self, obj: OrganizationUnit):
        return [{"id": child.id, "name": child.name, "code": child.code} for child in obj.children.all()]

    def get_manager_name(self, obj: OrganizationUnit) -> str:
        return obj.manager.get_full_name() if obj.manager else ""

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated or request.user.is_admin_role():
            return attrs

        operator = request.user
        parent = attrs.get("parent", getattr(self.instance, "parent", None))
        if not operator.org_unit_id:
            raise serializers.ValidationError("Managers must belong to an organization unit before managing org units.")
        if not parent or parent.id != operator.org_unit_id:
            raise serializers.ValidationError("Managers can only manage child organization units under their own organization unit.")
        return attrs

    def validate_code(self, value: str) -> str:
        normalized = value.strip().upper()
        queryset = OrganizationUnit.objects.filter(code__iexact=normalized)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        if queryset.exists():
            raise serializers.ValidationError("An organization unit with this code already exists.")
        return normalized

    def validate_name(self, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("Organization unit name is required.")
        return normalized

    def validate_parent(self, parent: OrganizationUnit | None) -> OrganizationUnit | None:
        if parent is None or self.instance is None:
            return parent

        if parent.id == self.instance.id:
            raise serializers.ValidationError("An organization unit cannot be its own parent.")

        current = parent
        while current is not None:
            if current.id == self.instance.id:
                raise serializers.ValidationError("An organization unit cannot use one of its descendants as parent.")
            current = current.parent

        return parent
