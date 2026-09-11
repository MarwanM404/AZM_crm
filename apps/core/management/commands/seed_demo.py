"""Seeds departments, branches, categories, and Arabic + English demo data (T126). Arabic
content in seed data means encoding and direction problems surface in every dev run and test,
not just at release."""

from django.core.management.base import BaseCommand

from apps.accounts.models import Branch, Department, User
from apps.tickets.models import Category


class Command(BaseCommand):
    help = "Seed departments, branches, categories, and demo users for local development."

    def handle(self, *args, **options):
        branch, _ = Branch.objects.get_or_create(
            name="Head Office", defaults={"name_ar": "المكتب الرئيسي"}
        )
        support_dept, _ = Department.objects.get_or_create(
            name="Support", defaults={"name_ar": "الدعم الفني"}
        )
        billing_dept, _ = Department.objects.get_or_create(
            name="Billing", defaults={"name_ar": "الفواتير"}
        )
        Category.objects.get_or_create(
            name="General inquiry",
            defaults={"name_ar": "استفسار عام", "department": support_dept},
        )
        Category.objects.get_or_create(
            name="Billing issue",
            defaults={"name_ar": "مشكلة في الفاتورة", "department": billing_dept},
        )

        if not User.objects.filter(email="agent@example.com").exists():
            User.objects.create_user(
                email="agent@example.com",
                password="demo-password-change-me",
                full_name="Demo Agent",
                role=User.Role.AGENT,
                department=support_dept,
                branch=branch,
            )
        if not User.objects.filter(email="admin@example.com").exists():
            User.objects.create_user(
                email="admin@example.com",
                password="demo-password-change-me",
                full_name="Demo Administrator",
                role=User.Role.ADMINISTRATOR,
                department=support_dept,
                branch=branch,
                is_staff=True,
            )

        self.stdout.write(self.style.SUCCESS("Seed data ready."))
