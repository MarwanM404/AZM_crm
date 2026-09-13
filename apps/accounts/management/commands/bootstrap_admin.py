"""
Create the first administrator, with a scope (FR-006).

Django's `createsuperuser` asks for the fields the model marks required, which here is an email
and a name. It cannot reasonably ask for a department: on an empty database there is none to
choose. So the account it creates has no scope, sees nothing, and looks like a broken product
to the person holding it — which is exactly how this defect was reported.

The department and the branch are created here, alongside the account, because that is the only
order in which the problem has a solution.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Branch, Department, User


class Command(BaseCommand):
    help = "Create the first administrator together with a department and a branch."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--full-name", required=True, dest="full_name")
        parser.add_argument("--department", required=True)
        parser.add_argument("--branch", required=True)

    @transaction.atomic
    def handle(self, *args, **options):
        email = (options["email"] or "").strip().lower()
        full_name = (options["full_name"] or "").strip()
        department_name = (options["department"] or "").strip()
        branch_name = (options["branch"] or "").strip()

        # Checked before anything is written, and the whole command runs in one transaction:
        # a half-run bootstrap would leave a department nobody asked for on a database whose
        # entire purpose was to be empty.
        if not email:
            raise CommandError("An email address is required.")
        if not full_name:
            raise CommandError("A full name is required.")
        if not department_name or not branch_name:
            raise CommandError(
                "A department and a branch are required. An administrator without them can "
                "see nothing, which is the defect this command exists to prevent."
            )
        if User.objects.filter(email=email).exists():
            raise CommandError(f"An account already exists for {email}.")

        department, _ = Department.objects.get_or_create(name=department_name)
        branch, _ = Branch.objects.get_or_create(name=branch_name)

        user = User(
            email=email,
            full_name=full_name,
            role=User.Role.ADMINISTRATOR,
            department=department,
            branch=branch,
            is_staff=True,
        )
        # No usable password, exactly as the administration screen does: creating an account
        # never creates a way in (MVP FR-025).
        user.set_unusable_password()
        user.save()

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {email} as an administrator in {department.name} · {branch.name}.\n"
                "Set a password before signing in:\n"
                f"    python manage.py changepassword {email}"
            )
        )
