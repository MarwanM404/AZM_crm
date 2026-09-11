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


@pytest.fixture
def contact(db, department, branch):
    from apps.customers.services.matching import find_or_create_contact

    contact, _ = find_or_create_contact(
        full_name="Sara Ahmed",
        email="sara@najd-trading.example",
        department=department,
        branch=branch,
    )
    return contact


@pytest.fixture
def ticket(db, department, branch, category, contact):
    from apps.tickets.models import Ticket

    return Ticket.objects.create(
        contact=contact,
        organization=contact.organization,
        subject="Shipment marked delivered but not received",
        description="Nothing arrived at our office.",
        category=category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=department,
        branch=branch,
    )


@pytest.fixture
def other_department_ticket(db, other_department, branch, contact):
    from apps.tickets.models import Category, Ticket

    other_category = Category.objects.create(name="Billing", department=other_department)
    return Ticket.objects.create(
        contact=contact,
        subject="Invoice query from another department",
        description="...",
        category=other_category,
        origin_channel=Ticket.Channel.WEB_FORM,
        department=other_department,
        branch=branch,
    )


@pytest.fixture
def agent_client(db, agent):
    """Its OWN Client, not pytest-django's shared `client`.

    Several tests need two people signed in at once — an administrator deactivating an agent
    who still holds a live session is the whole point of FR-026. Sharing one client makes the
    second force_login silently replace the first, and the test then asserts something it is
    not actually exercising.
    """
    from django.test import Client

    own = Client()
    own.force_login(agent)
    return own


@pytest.fixture
def admin_client_(db, administrator):
    from django.test import Client

    own = Client()
    own.force_login(administrator)
    return own


@pytest.fixture
def other_agent(db, department, branch):
    """A colleague in the SAME department — FR-038 gives them the same ticket visibility,
    which is what makes the shared pull queue contested and the 409 on take meaningful."""
    return User.objects.create_user(
        email="colleague@example.com",
        password="pw",
        full_name="Omar Saleh",
        role=User.Role.AGENT,
        department=department,
        branch=branch,
    )


@pytest.fixture
def english_agent_client(db, agent):
    """An agent whose interface language is English.

    The default User language is Arabic, which is correct for this business — so any test
    asserting English interface copy must say so, rather than depending on the preference
    not being applied. Tests about behaviour rather than wording should prefer `agent_client`.
    """
    from django.test import Client

    agent.language = "en"
    agent.save(update_fields=["language"])
    own = Client()
    own.force_login(agent)
    return own
