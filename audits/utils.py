from ipaddress import ip_address as parse_ip_address

from .models import AuditLog


def create_audit_log(request, action: str, target, changes: dict | None = None, metadata: dict | None = None) -> AuditLog:
    target_model = target.__name__ if isinstance(target, type) else target.__class__.__name__
    target_id = "" if isinstance(target, type) else str(getattr(target, "pk", ""))
    target_repr = target_model if isinstance(target, type) else str(target)
    actor = getattr(request, "user", None)
    ip_address = None
    metadata = metadata.copy() if metadata else {}
    if request:
        remote_address = request.META.get("REMOTE_ADDR")
        try:
            ip_address = str(parse_ip_address(remote_address.strip())) if remote_address else None
        except (ValueError, AttributeError):
            ip_address = None
        metadata.setdefault("method", request.method)
        metadata.setdefault("path", request.path)
    if not getattr(actor, "is_authenticated", False):
        actor = None

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        target_model=target_model,
        target_id=target_id,
        target_repr=target_repr,
        changes=changes or {},
        metadata=metadata,
        ip_address=ip_address,
    )
