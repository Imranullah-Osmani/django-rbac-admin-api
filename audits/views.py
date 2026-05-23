from rest_framework import mixins, viewsets

from accounts.permissions import IsInternalAdmin

from .models import AuditLog
from .serializers import AuditLogSerializer


class AuditLogViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    queryset = AuditLog.objects.select_related("actor").order_by("-created_at", "-id")
    serializer_class = AuditLogSerializer
    permission_classes = [IsInternalAdmin]
    search_fields = ("action", "target_model", "target_repr", "actor__email")
    ordering_fields = ("created_at", "action", "target_model")
    ordering = ("-created_at", "-id")
