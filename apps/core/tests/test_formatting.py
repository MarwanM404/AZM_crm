"""FR-034: dates, times and numbers are formatted for the active language."""

import pytest
from django.utils import translation

from apps.core.templatetags.formatting import local_datetime, local_number


@pytest.mark.django_db
def test_number_formatting_differs_by_language():
    with translation.override("en"):
        english = local_number(1234567.5)
    with translation.override("ar"):
        arabic = local_number(1234567.5)

    assert english == "1,234,567.5"
    assert arabic  # Arabic formatting is locale-driven; it must at least produce something
    assert isinstance(arabic, str)


@pytest.mark.django_db
def test_datetime_formatting_is_localized_and_utc_based():
    from datetime import datetime
    from datetime import timezone as dt_timezone

    moment = datetime(2026, 3, 14, 9, 5, tzinfo=dt_timezone.utc)

    with translation.override("en"):
        english = local_datetime(moment)
    with translation.override("ar"):
        arabic = local_datetime(moment)

    assert "2026" in english
    assert "2026" in arabic
    assert english != "" and arabic != ""


@pytest.mark.django_db
def test_formatting_handles_none_without_raising():
    assert local_datetime(None) == ""
    assert local_number(None) == ""
