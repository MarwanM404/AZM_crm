from apps.core.models_sequence import allocate_reference


def next_organization_reference() -> str:
    return allocate_reference("ORG")
