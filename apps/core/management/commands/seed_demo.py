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
        if not User.objects.filter(email="supervisor@example.com").exists():
            # Seeded so the third role is exercised in every development run rather than only
            # in tests — a role nobody signs in as is a role whose screens rot.
            User.objects.create_user(
                email="supervisor@example.com",
                password="demo-password-change-me",
                full_name="Demo Supervisor",
                role=User.Role.SUPERVISOR,
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

        self._seed_customers(support_dept, branch)
        self.stdout.write(self.style.SUCCESS("Seed data ready."))

    def _seed_customers(self, department, branch):
        """Arabic content in the seed data means encoding and direction problems surface in
        every development run, not at release (T126). A demo dataset that is entirely Latin
        makes an Arabic-first product look fine right up until a real customer writes in."""
        from apps.customers.models import Organization
        from apps.customers.services.matching import find_or_create_contact
        from apps.tickets.models import Category, Message, Ticket

        org, _ = Organization.objects.get_or_create(
            name="Najd Trading Co.",
            defaults={"name_ar": "شركة نجد التجارية", "department": department, "branch": branch},
        )
        category = Category.objects.filter(department=department).first()
        if category is None:
            return

        sara, created = find_or_create_contact(
            full_name="سارة أحمد",
            email="sara.ahmed@najd-trading.example",
            department=department,
            branch=branch,
        )
        if created:
            sara.organization = org
            sara.preferred_language = "ar"
            sara.save(update_fields=["organization", "preferred_language"])

        if not Ticket.objects.filter(contact=sara).exists():
            arabic_ticket = Ticket.objects.create(
                contact=sara,
                organization=org,
                subject="لم يصل الشحن رغم تسجيله كمُسلَّم",
                description="تُظهر صفحة التتبّع أن الشحنة سُلِّمت أمس، لكن لم يصل شيء إلى مكتبنا.",
                category=category,
                priority=Ticket.Priority.URGENT,
                origin_channel=Ticket.Channel.WEB_FORM,
                department=department,
                branch=branch,
            )
            Message.objects.create(
                ticket=arabic_ticket,
                author=None,
                direction=Message.Direction.INBOUND,
                visibility=Message.Visibility.PUBLIC,
                channel=Ticket.Channel.WEB_FORM,
                body="نحتاج هذه القطع قبل يوم الأحد.",
            )

        english_contact, created_en = find_or_create_contact(
            full_name="Omar Khalid",
            email="omar.k@najd-trading.example",
            department=department,
            branch=branch,
        )
        if created_en:
            english_contact.organization = org
            english_contact.preferred_language = "en"
            english_contact.save(update_fields=["organization", "preferred_language"])
            Ticket.objects.create(
                contact=english_contact,
                organization=org,
                subject="Invoice total does not match the order",
                description="The March invoice is higher than the order we approved.",
                category=category,
                priority=Ticket.Priority.HIGH,
                origin_channel=Ticket.Channel.EMAIL,
                department=department,
                branch=branch,
            )
