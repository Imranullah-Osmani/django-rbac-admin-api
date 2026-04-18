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
