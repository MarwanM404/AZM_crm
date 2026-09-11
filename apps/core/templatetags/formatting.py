"""
Locale-aware date, time and number formatting (FR-034).

Django localizes through the active language, so these are thin wrappers rather than
reimplementations — the value of having them in one place is that every screen formats the
same way, and that `None` renders as an empty string rather than the literal "None", which is
what naive template output produces.

Timestamps are stored in UTC (constitution: all timestamps in UTC) and converted for display
only here.
"""

from django import template
from django.utils import formats, timezone

register = template.Library()


@register.filter
def local_datetime(value):
    """A timestamp in the active locale's format, converted from UTC to local time."""
    if value is None:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return formats.date_format(value, format="DATETIME_FORMAT", use_l10n=True)


@register.filter
def local_date(value):
    if value is None:
        return ""
    if timezone.is_aware(value):
        value = timezone.localtime(value)
    return formats.date_format(value, format="DATE_FORMAT", use_l10n=True)


@register.filter
def local_number(value):
    """A number with the active locale's grouping and decimal separators."""
    if value is None:
        return ""
    return formats.number_format(value, use_l10n=True, force_grouping=True)
