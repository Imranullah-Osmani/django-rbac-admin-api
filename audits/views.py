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

    def get_queryset(self):
        queryset = super().get_queryset()
        action = self.request.query_params.get("action")
        target_model = self.request.query_params.get("target_model")
        actor_email = self.request.query_params.get("actor_email")
        if action:
            queryset = queryset.filter(action=action.strip().lower())
        if target_model:
            queryset = queryset.filter(target_model__iexact=target_model.strip())
        if actor_email:
            queryset = queryset.filter(actor__email__iexact=actor_email.strip())
        return queryset
