import pytest
from django.core.cache import cache

from apps.accounts.models import Branch, Department, User
from apps.tickets.models import Category


@pytest.fixture(autouse=True)
def clear_cache():
    """django-ratelimit's counters live in Django's cache. LocMemCache is shared across the
    whole test process, so without this, submissions from one test count toward another
    test's rate limit — a real isolation bug this project hit once already."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def department(db):
    return Department.objects.create(name="Support", name_ar="الدعم")


@pytest.fixture
def other_department(db):
    return Department.objects.create(name="Billing", name_ar="الفواتير")


@pytest.fixture
def branch(db):
    return Branch.objects.create(name="Head Office", name_ar="المكتب الرئيسي")


@pytest.fixture
def category(db, department):
    return Category.objects.create(name="General", name_ar="عام", department=department)


@pytest.fixture
def agent(db, department, branch):
    return User.objects.create_user(
        email="agent@example.com",
        password="pw",
        full_name="Agent One",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )


@pytest.fixture
def other_department_agent(db, other_department, branch):
    return User.objects.create_user(
        email="agent2@example.com",
        password="pw",
        full_name="Agent Two",
        role=User.Role.AGENT,
        department=other_department,
        branch=branch,
    )


@pytest.fixture
def administrator(db, department, branch):
    return User.objects.create_user(
        email="admin@example.com",
        password="pw",
        full_name="Admin One",
        role=User.Role.ADMINISTRATOR,
        department=department,
        branch=branch,
        is_staff=True,
    )
