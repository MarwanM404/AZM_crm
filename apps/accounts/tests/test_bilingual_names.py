"""
Department and branch names in the reader's language (T026, T032, T033, FR-008).

Both models have carried a second name since the MVP and nothing has ever read it. So every
place that displays a department displays the English one, including to an Arabic reader on an
otherwise Arabic screen — the administration dropdowns being the visible case.

The fix is one property on the model rather than a choice at each display site, because there
are several display sites and they currently all make the same wrong choice independently.
"""

import pytest
from django.urls import reverse
from django.utils import translation

from apps.accounts.models import Branch, Department

pytestmark = pytest.mark.django_db


def test_the_arabic_name_is_used_for_an_arabic_reader():
    department = Department.objects.create(name="Support", name_ar="الدعم الفني")

    with translation.override("ar"):
        assert department.display_name == "الدعم الفني"


def test_the_english_name_is_used_for_an_english_reader():
    department = Department.objects.create(name="Support", name_ar="الدعم الفني")

    with translation.override("en"):
        assert department.display_name == "Support"


def test_a_missing_arabic_name_falls_back_to_the_english_one():
    """A missing translation should degrade to a readable name, not to an empty cell — an
    unnamed department in a dropdown is worse than an untranslated one."""
    department = Department.objects.create(name="Support", name_ar="")

    with translation.override("ar"):
        assert department.display_name == "Support"


def test_branches_behave_the_same_way():
    branch = Branch.objects.create(name="Head Office", name_ar="المكتب الرئيسي")

    with translation.override("ar"):
        assert branch.display_name == "المكتب الرئيسي"
    with translation.override("en"):
        assert branch.display_name == "Head Office"


def test_the_add_account_dropdowns_show_the_readers_language(admin_client_, administrator):
    """The visible case: an Arabic administration screen listing "Billing" and "Support"."""
    administrator.language = "ar"
    administrator.save(update_fields=["language"])
    administrator.department.name_ar = "الدعم الفني"
    administrator.department.save(update_fields=["name_ar"])
    administrator.branch.name_ar = "المكتب الرئيسي"
    administrator.branch.save(update_fields=["name_ar"])

    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    assert "الدعم الفني" in body
    assert "المكتب الرئيسي" in body


def test_the_english_reader_still_sees_english(admin_client_, administrator):
    administrator.language = "en"
    administrator.save(update_fields=["language"])
    administrator.department.name_ar = "الدعم الفني"
    administrator.department.save(update_fields=["name_ar"])

    body = admin_client_.get(reverse("administration:user_new")).content.decode()

    assert administrator.department.name in body


def test_the_scope_notice_dropdowns_use_it_too(client, db, department, branch):
    """The notice added by User Story 2 lists departments as well, and a screen added to fix
    one bilingual gap should not open another."""
    from apps.accounts.models import User

    department.name_ar = "الدعم الفني"
    department.save(update_fields=["name_ar"])
    scopeless = User.objects.create_superuser(
        email="root@example.com", password="x", full_name="Root", language="ar"
    )
    client.force_login(scopeless)

    body = client.get(reverse("administration:users")).content.decode()

    assert "الدعم الفني" in body
