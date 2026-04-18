from .models import AuditLog


def create_audit_log(request, action: str, target, changes: dict | None = None, metadata: dict | None = None) -> AuditLog:
    target_model = target.__name__ if isinstance(target, type) else target.__class__.__name__
    target_id = "" if isinstance(target, type) else str(getattr(target, "pk", ""))
    target_repr = target_model if isinstance(target, type) else str(target)
    actor = getattr(request, "user", None)
    ip_address = None
    if request:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        ip_address = (forwarded.split(",")[0] if forwarded else request.META.get("REMOTE_ADDR")) or None
    if not getattr(actor, "is_authenticated", False):
        actor = None

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model=target_model,
        target_id=target_id,
        target_repr=target_repr,
        changes=changes or {},
        metadata=metadata or {},
        ip_address=ip_address,
    )

