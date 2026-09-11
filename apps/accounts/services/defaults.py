"""The organization runs a single branch at launch (roadmap.md, research.md #8); the data
model already supports several. This is the one place that assumption lives, so multi-branch
operation later is a data change here, not a redesign."""

from apps.accounts.models import Branch


def default_branch() -> Branch:
    branch = Branch.objects.filter(is_active=True).order_by("pk").first()
    if branch is None:
        raise RuntimeError(
            "No active Branch configured. Seed at least one Branch before intake can run."
        )
    return branch
