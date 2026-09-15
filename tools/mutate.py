"""
Break each guarantee in turn and record which checks notice (spec 004, FR-038).

A test suite that has never been seen to fail is a suite nobody has tested. This applies each
defect the customer portal is supposed to prevent, runs the tests, and writes down what broke —
so the claim "this is covered" is backed by an observation rather than by the presence of a
file with the right name.

Every patch asserts that it matched. An earlier round of this in spec 003 had two mutations
that silently never applied, and a mutation that does not apply reports the codebase as
perfectly defended.

    python tools/mutate.py            # run them all, print a table
    python tools/mutate.py --list     # names only
"""

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent


#: (name, what it breaks, file, before, after, test scope)
def M(name, breaks, path, before, after, scope):
    """One defect, as data. Written through a helper so the before/after blocks can be
    triple-quoted — a table of one-line string literals containing embedded newlines is
    unreadable at exactly the moment somebody needs to check that a patch still matches."""
    return {
        "name": name,
        "breaks": breaks,
        "path": path,
        "before": before.strip("\n"),
        "after": after.strip("\n"),
        "scope": scope,
    }


MUTATIONS = [
    M(
        "staff refusal",
        "a customer session satisfies the deny-by-default wall anywhere, not only portal paths",
        "apps/core/middleware.py",
        """
        from apps.portal.middleware import is_portal_path

        return is_portal_path(request)
""",
        """
        return True
""",
        "apps/portal/tests/test_staff_routes_refuse_customers.py",
    ),
    M(
        "staff session survives",
        "the portal signs a staff member out instead of refusing them",
        "apps/portal/middleware.py",
        """
        return render(
            request,
            "core/portal_is_for_customers.html",
""",
        """
        request.session.flush()
        return render(
            request,
            "core/portal_is_for_customers.html",
""",
        "apps/portal/tests/test_staff_are_not_customers.py",
    ),
    M(
        "confirmation gate",
        "an account that has not proved its address may use the portal",
        "apps/portal/models.py",
        """
        return self.is_active and self.is_confirmed
""",
        """
        return self.is_active
""",
        "apps/portal/tests",
    ),
    M(
        "identical response",
        "registration answers differently for an address that already has an account",
        "apps/portal/services/registration.py",
        """
    if account.is_confirmed:
""",
        """
    if account.is_confirmed:
        raise ValueError("address already registered")
""",
        "apps/portal/tests/test_registration.py",
    ),
    M(
        "internal boundary",
        "the request detail reads the staff message filter instead of the customer one",
        "apps/portal/services/tickets.py",
        """
    return public_messages_for(ticket).select_related("author")
""",
        """
    return ticket.messages.all().order_by("created_at").select_related("author")
""",
        "apps/portal/tests/test_request_detail.py tests/test_internal_visibility.py",
    ),
    M(
        "narrow context",
        "the detail template is handed the ticket, so it can walk to an internal note",
        "apps/portal/services/tickets.py",
        """
    return customer_facing_context(
        ticket,
        description=ticket.description,
""",
        """
    return customer_facing_context(
        ticket,
        ticket=ticket,
        description=ticket.description,
""",
        "apps/portal/tests/test_request_detail.py",
    ),
    M(
        "address scoping",
        "the request list filters by organization, so colleagues' requests appear",
        "apps/portal/services/tickets.py",
        """
        Ticket.objects.filter(contact_id__in=contact_ids_for(account))
""",
        """
        Ticket.objects.filter(
            contact__organization__contacts__id__in=contact_ids_for(account)
        )
""",
        "apps/portal/tests/test_request_list.py",
    ),
    M(
        "reply parity",
        "the portal decides the reply's effect on the ticket rather than sharing the rule",
        "apps/portal/services/tickets.py",
        """
        reopen_for_customer_reply(ticket)
""",
        """
        if ticket.status in ("RESOLVED", "PENDING_CUSTOMER"):
            ticket.status = "OPEN"
            ticket.save(update_fields=["status"])
""",
        "apps/portal/tests/test_reply.py apps/portal/tests/test_reply_parity.py",
    ),
    M(
        "not-found refusal",
        "somebody else's request is refused as forbidden rather than as not found",
        "apps/portal/views.py",
        """
    ticket = tickets.request_for(request.customer, reference)
    if ticket is None:
        raise Http404("No such request")
""",
        """
    from django.core.exceptions import PermissionDenied

    from apps.tickets.models import Ticket as AnyTicket

    ticket = tickets.request_for(request.customer, reference)
    if ticket is None:
        if AnyTicket.objects.filter(reference=reference).exists():
            raise PermissionDenied("not yours")
        raise Http404("No such request")
""",
        "apps/portal/tests/test_request_detail.py",
    ),
    M(
        "password policy",
        "the strength check is given no account, so the similarity validator approves everything",
        "apps/portal/services/passwords.py",
        """
    validate_password(password or "", user=CustomerAccount(email=email or ""))
""",
        """
    validate_password(password or "", user=None)
""",
        "apps/portal/tests/test_password_policy.py",
    ),
    M(
        "session invalidation",
        "a password change leaves every other session alive",
        "apps/portal/auth.py",
        """
    stamped = session.get(CUSTOMER_SESSION_FINGERPRINT, "")
    if not constant_time_compare(stamped, account.session_fingerprint):
        return None
""",
        """
    pass
""",
        "apps/portal/tests/test_password_reset.py",
    ),
    M(
        "sign-in lockout",
        "the lock opens for the correct password",
        "apps/portal/auth.py",
        """
    if account.is_locked:
        check_password(password or "", _ABSENT_ACCOUNT_HASH)
        return None
""",
        """
    pass
""",
        "apps/portal/tests/test_lockout.py",
    ),
    M(
        "customer language",
        "the portal ignores the language the customer chose",
        "apps/portal/middleware.py",
        """
        return self.serve_in_the_customers_language(request)
""",
        """
        return self.get_response(request)
""",
        "apps/portal/tests/test_portal_language.py",
    ),
    M(
        "content limit",
        "customer-authored content is accepted at any length",
        "apps/portal/forms.py",
        """
    if len(text) > limit:
""",
        """
    if False:
""",
        "apps/portal/tests/test_reply.py apps/portal/tests/test_new_request.py",
    ),
    M(
        "shared creation",
        "a new contact's language preference is dropped",
        "apps/intake/services/creation.py",
        """
    if created:
        contact.preferred_language = language
        contact.save(update_fields=["preferred_language"])
""",
        """
    pass
""",
        "apps/portal/tests/test_new_request.py apps/intake/tests/test_public_form_is_unchanged.py",
    ),
]


def run(scope):
    command = [".venv/bin/python", "-m", "pytest", *scope.split()]
    command += ["-q", "-p", "no:cacheprovider", "--no-cov"]
    result = subprocess.run(
        command,
        cwd=BASE,
        capture_output=True,
        text=True,
    )
    failures = re.findall(r"^FAILED (\S+)", result.stdout, re.MULTILINE)
    errors = re.findall(r"^ERROR (\S+)", result.stdout, re.MULTILINE)
    return failures + errors


def apply(path, before, after):
    source = path.read_text(encoding="utf-8")
    if before not in source:
        raise SystemExit(
            f"MUTATION DID NOT APPLY in {path}. A mutation that does not apply reports the "
            "codebase as perfectly defended, which is the one result this tool must never "
            "produce by accident."
        )
    path.write_text(source.replace(before, after, 1), encoding="utf-8")


def main():
    if "--list" in sys.argv:
        for mutation in MUTATIONS:
            print(f"{mutation['name']}: {mutation['breaks']}")
        return 0

    results, undetected = [], []

    for mutation in MUTATIONS:
        name, breaks = mutation["name"], mutation["breaks"]
        scope = mutation["scope"]
        path = BASE / mutation["path"]
        with tempfile.TemporaryDirectory() as keep:
            backup = Path(keep) / path.name
            shutil.copy2(path, backup)
            try:
                apply(path, mutation["before"], mutation["after"])
                caught = run(scope)
            finally:
                shutil.copy2(backup, path)

        results.append((name, breaks, caught))
        if not caught:
            undetected.append(name)
        print(f"{'FAIL' if not caught else 'ok  '}  {name}: {len(caught)} check(s) noticed")

    print("\n--- restored; confirming the suite is green ---")
    left_broken = run("apps tests -m 'not e2e'")
    if left_broken:
        print("THE TREE WAS LEFT BROKEN:", left_broken[:5])
        return 1

    if undetected:
        print("\nUNDETECTED:", ", ".join(undetected))
        return 1

    print("Every mutation was detected and the tree is clean.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
