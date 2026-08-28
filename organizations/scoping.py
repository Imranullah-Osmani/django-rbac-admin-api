from .models import OrganizationUnit


def organization_branch_ids(root_id) -> list[int]:
    branch_ids = [root_id]
    frontier = [root_id]

    while frontier:
        child_ids = list(OrganizationUnit.objects.filter(parent_id__in=frontier).values_list("id", flat=True))
        branch_ids.extend(child_ids)
        frontier = child_ids

    return branch_ids
