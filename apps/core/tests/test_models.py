import pytest

from apps.customers.models import Organization


@pytest.mark.django_db
def test_timestamped_model_sets_utc_timestamps(department, branch):
    org = Organization.objects.create(name="Acme", department=department, branch=branch)
    assert org.created_at is not None
    assert org.updated_at is not None
    assert org.created_at.tzinfo is not None  # USE_TZ=True; naive datetimes would fail this


@pytest.mark.django_db
def test_soft_delete_hides_from_default_manager_but_not_all_objects(department, branch, agent):
    org = Organization.objects.create(name="Acme", department=department, branch=branch)
    org.soft_delete(by=agent)

    assert not Organization.objects.filter(pk=org.pk).exists()
    assert Organization.all_objects.filter(pk=org.pk).exists()

    recovered = Organization.all_objects.get(pk=org.pk)
    assert recovered.is_deleted
    assert recovered.deleted_by == agent
    assert recovered.deleted_at is not None
