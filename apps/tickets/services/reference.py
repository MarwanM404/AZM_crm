"""AZM-{year}-{sequence}, per research.md #4."""

from apps.core.models_sequence import allocate_reference


def next_ticket_reference() -> str:
    return allocate_reference("AZM")
