from .models import OrganizationUnit


def organization_branch_ids(root_id) -> list[int]:
    if root_id is None:
        return []

    branch_ids = [root_id]
    visited = {root_id}
    frontier = [root_id]

    while frontier:
        child_ids = list(
            OrganizationUnit.objects.filter(parent_id__in=frontier)
            .exclude(id__in=visited).order_by("id").values_list("id", flat=True)
        )
        branch_ids.extend(child_ids)
        visited.update(child_ids)
        frontier = child_ids

    return branch_ids
