from django.contrib.auth.models import Permission
from rest_framework import serializers

from .models import Role, User


class PermissionSerializer(serializers.ModelSerializer):
    app_label = serializers.CharField(source="content_type.app_label", read_only=True)
    model = serializers.CharField(source="content_type.model", read_only=True)

    class Meta:
        model = Permission
        fields = ("id", "name", "codename", "app_label", "model")


class RoleSerializer(serializers.ModelSerializer):
    permission_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=Permission.objects.all(),
        source="permissions",
        required=False,
    )
    permissions = PermissionSerializer(many=True, read_only=True)
    user_count = serializers.SerializerMethodField()

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "slug",
            "description",
            "is_system",
            "permissions",
            "permission_ids",
            "user_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("name", "slug", "is_system", "created_at", "updated_at")

    def get_user_count(self, obj: Role) -> int:
        return obj.users.count()


class UserSerializer(serializers.ModelSerializer):
    role_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        write_only=True,
        queryset=Role.objects.all(),
        source="roles",
        required=False,
    )
    roles = RoleSerializer(many=True, read_only=True)
    effective_permissions = serializers.SerializerMethodField()
    org_unit_name = serializers.CharField(source="org_unit.name", read_only=True)
    primary_role = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "title",
            "phone_number",
            "org_unit",
            "org_unit_name",
            "roles",
            "primary_role",
            "role_ids",
            "is_active",
            "is_staff",
            "date_joined",
            "effective_permissions",
        )
        read_only_fields = ("date_joined",)

    def get_effective_permissions(self, obj: User) -> list[str]:
        return obj.effective_permissions()

    def get_primary_role(self, obj: User) -> str:
        return obj.role_slugs[0] if obj.role_slugs else ""

    def validate(self, attrs):
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return attrs

        roles = attrs.get("roles")
        org_unit = attrs.get("org_unit")
        operator = request.user

        if operator.is_admin_role():
            return attrs

        if roles and any(role.slug == "admin" for role in roles):
            raise serializers.ValidationError("Managers cannot assign the admin role.")

        target_org_unit = org_unit if org_unit is not None else getattr(self.instance, "org_unit", None)
        if not operator.org_unit_id:
            raise serializers.ValidationError("Managers must belong to an organization unit before managing users.")
        if target_org_unit is None:
            raise serializers.ValidationError("Managers can only manage users assigned to their organization unit.")
        if target_org_unit.id != operator.org_unit_id:
            raise serializers.ValidationError("Managers can only manage users inside their own organization unit.")

        return attrs
