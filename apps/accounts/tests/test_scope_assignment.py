"""FR-025: changing a user's department changes what they can reach, and is audited."""

import pytest
from auditlog.models import LogEntry
from django.urls import reverse


@pytest.mark.django_db
def test_moving_an_agent_changes_what_they_can_see(
    client, admin_client_, agent, ticket, other_department
):
    client.force_login(agent)
    assert ticket.reference in client.get(reverse("tickets:queue")).content.decode()

    admin_client_.post(
        reverse("administration:user_scope", args=[agent.pk]),
        {"department": other_department.pk, "branch": agent.branch.pk},
    )

    client.force_login(agent)  # re-authenticate; the session survived, the scope did not
    body = client.get(reverse("tickets:queue")).content.decode()
    assert ticket.reference not in body


@pytest.mark.django_db
def test_moving_an_agent_is_audited(admin_client_, agent, other_department):
    admin_client_.post(
        reverse("administration:user_scope", args=[agent.pk]),
        {"department": other_department.pk, "branch": agent.branch.pk},
    )
    assert LogEntry.objects.get_for_object(agent).exists()


@pytest.mark.django_db
def test_a_moved_agent_gets_404_on_their_old_tickets(
    client, admin_client_, agent, ticket, other_department
):
    admin_client_.post(
        reverse("administration:user_scope", args=[agent.pk]),
        {"department": other_department.pk, "branch": agent.branch.pk},
    )
    client.force_login(agent)

    response = client.get(reverse("tickets:detail", args=[ticket.reference]))
    assert response.status_code == 404  # not 403 — FR-024
