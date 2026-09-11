"""A per-year, per-prefix allocator backing human-quotable references (research.md #4).

Uses select_for_update so concurrent requests never allocate the same number — this is the
mechanism behind the uniqueness guarantee in FR-003 and apps/tickets/tests/test_reference.py.
"""

from django.db import models, transaction


class ReferenceSequence(models.Model):
    prefix = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("prefix", "year")]

    def __str__(self):
        return f"{self.prefix}-{self.year}: {self.last_value}"

    @classmethod
    def next_value(cls, prefix: str, year: int) -> int:
        with transaction.atomic():
            seq, _ = cls.objects.select_for_update().get_or_create(prefix=prefix, year=year)
            seq.last_value += 1
            seq.save(update_fields=["last_value"])
            return seq.last_value


def allocate_reference(prefix: str) -> str:
    from django.utils import timezone

    year = timezone.now().year
    value = ReferenceSequence.next_value(prefix, year)
    return f"{prefix}-{year}-{value:06d}"
