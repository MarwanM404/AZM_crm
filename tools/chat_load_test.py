"""
T126: 150 concurrent conversations against the assumed 50 agents.

Run as a script, not a test:

    python tools/chat_load_test.py

It records a measurement rather than asserting a timing. A timing assertion in the suite fails
on a loaded CI machine for reasons that have nothing to do with the code, and the usual next
step is to loosen it until it stops failing — at which point it is measuring nothing. The
numbers belong in docs/operations.md, beside the conditions they were taken under.
"""

import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import django  # noqa: E402

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.test")
django.setup()

from django.test.runner import DiscoverRunner  # noqa: E402
from django.test.utils import setup_test_environment, teardown_test_environment  # noqa: E402

setup_test_environment()
runner = DiscoverRunner(verbosity=0, interactive=False)
old_config = runner.setup_databases()

from apps.accounts.models import Branch, Department, User  # noqa: E402
from apps.chat.services import lifecycle, presence, queue  # noqa: E402
from apps.chat.services.redis_client import reset_for_tests  # noqa: E402
from apps.customers.services.matching import find_or_create_contact  # noqa: E402
from apps.tickets.models import Category  # noqa: E402

AGENTS = 50
CAPACITY = 3
CONVERSATIONS = 150

try:
    reset_for_tests()
    department = Department.objects.create(name="Support")
    branch = Branch.objects.create(name="Head Office")
    category = Category.objects.create(name="General", department=department)

    agents = [
        User.objects.create_user(
            email=f"agent{i}@example.com",
            password="x",
            full_name=f"Agent {i}",
            role=User.Role.AGENT,
            department=department,
            branch=branch,
        )
        for i in range(AGENTS)
    ]
    for agent in agents:
        presence.go_online(agent.pk, capacity=CAPACITY)

    starts, assigns = [], []
    assigned = queued = 0
    for i in range(CONVERSATIONS):
        contact, _ = find_or_create_contact(
            full_name=f"Visitor {i}",
            email=f"v{i}@example.com",
            department=department,
            branch=branch,
        )
        t0 = time.perf_counter()
        conversation, _token = lifecycle.start(
            contact=contact,
            department=department,
            branch=branch,
            category=category,
            subject=f"Question {i}",
        )
        t1 = time.perf_counter()
        agent_id = lifecycle.try_assign(
            conversation, lifecycle.candidate_agents(department.pk, branch.pk)
        )
        t2 = time.perf_counter()
        starts.append((t1 - t0) * 1000)
        assigns.append((t2 - t1) * 1000)
        assigned += 1 if agent_id else 0
        queued += 0 if agent_id else 1

    # Fifty agents at capacity three is exactly 150 slots, so the run above never touches the
    # queue. Another fifty arrivals is what actually measures waiting.
    OVERSUBSCRIBED = 50
    joins, positions = [], []
    for i in range(CONVERSATIONS, CONVERSATIONS + OVERSUBSCRIBED):
        contact, _ = find_or_create_contact(
            full_name=f"Visitor {i}",
            email=f"v{i}@example.com",
            department=department,
            branch=branch,
        )
        conversation, _token = lifecycle.start(
            contact=contact,
            department=department,
            branch=branch,
            category=category,
            subject=f"Question {i}",
        )
        t0 = time.perf_counter()
        lifecycle.try_assign(conversation, lifecycle.candidate_agents(department.pk, branch.pk))
        t1 = time.perf_counter()
        queue.position(str(conversation.pk), department.pk, branch.pk)
        t2 = time.perf_counter()
        joins.append((t1 - t0) * 1000)
        positions.append((t2 - t1) * 1000)

    def p95(xs):
        return statistics.quantiles(xs, n=20)[-1]

    print(f"agents:            {AGENTS} x capacity {CAPACITY} = {AGENTS * CAPACITY} slots")
    print(f"conversations:     {CONVERSATIONS}")
    print(f"assigned:          {assigned}")
    print(f"queued:            {queued}")
    print(f"queue depth:       {queue.waiting_count(department.pk, branch.pk)}")
    print(f"start   median/p95: {statistics.median(starts):.1f} / {p95(starts):.1f} ms")
    print(f"assign  median/p95: {statistics.median(assigns):.1f} / {p95(assigns):.1f} ms")
    print()
    print(f"oversubscribed by: {OVERSUBSCRIBED}")
    print(f"queue depth:       {queue.waiting_count(department.pk, branch.pk)}")
    print(f"refuse+queue median/p95: {statistics.median(joins):.1f} / {p95(joins):.1f} ms")
    print(f"position    median/p95: {statistics.median(positions):.3f} / {p95(positions):.3f} ms")
finally:
    runner.teardown_databases(old_config)
    teardown_test_environment()
