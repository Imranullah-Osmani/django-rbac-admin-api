from rest_framework.permissions import BasePermission


class IsInternalAdmin(BasePermission):
    message = "You need an internal admin role to manage this resource."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.has_internal_access())


class IsAdminRole(BasePermission):
    message = "Only admins can manage this resource."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_admin_role())


class IsAdminOrManager(BasePermission):
    message = "This resource is limited to admins and managers."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_manager_role())
