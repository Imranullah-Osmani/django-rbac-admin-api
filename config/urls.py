from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.views import PermissionViewSet, RoleViewSet, UserViewSet
from audits.views import AuditLogViewSet
from config.views import health_live, health_ready, home
from organizations.views import OrganizationUnitViewSet


router = DefaultRouter()
router.register("users", UserViewSet, basename="user")
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", PermissionViewSet, basename="permission")
router.register("audit-logs", AuditLogViewSet, basename="audit-log")
router.register("org-units", OrganizationUnitViewSet, basename="org-unit")

urlpatterns = [
    path("", home, name="home"),
    path("health/live/", health_live, name="health-live"),
    path("health/ready/", health_ready, name="health-ready"),
    path("admin/", admin.site.urls),
    path("api/auth/token/", TokenObtainPairView.as_view(), name="api-token"),
    path("api/auth/token/refresh/", TokenRefreshView.as_view(), name="api-token-refresh"),
    path("api-auth/", include("rest_framework.urls")),
    path("api/", include(router.urls)),
]
