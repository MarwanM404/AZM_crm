"""
Department, Branch, and the custom User model.

FR-022: two fixed roles, Agent and Administrator, not user-configurable in the MVP.
FR-025: administrators manage accounts, each with exactly one role and at least one
department/branch.
FR-026: deactivation MUST terminate access immediately, not merely at next sign-in.
"""

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.contrib.sessions.models import Session
from django.db import models
from django.db.models.functions import Now
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class Department(TimeStampedModel):
    """Organizational unit that scopes visibility (FR-023)."""

    name = models.CharField(_("name"), max_length=150)
    name_ar = models.CharField(_("name (Arabic)"), max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        """The name in the reader's language, falling back to the other when blank.

        A property rather than a choice at each display site: the second name has been stored
        since the MVP and read nowhere, which means every site that shows a department made
        the same wrong choice independently. One property makes it once.

        Falling back to `name` matters — a missing translation should degrade to a readable
        name, and an unnamed department in a dropdown is worse than an untranslated one.
        """
        from django.utils.translation import get_language

        if (get_language() or "").startswith("ar") and self.name_ar:
            return self.name_ar
        return self.name


class Branch(TimeStampedModel):
    """Location that scopes visibility (FR-023). One row at launch; the model supports many."""

    name = models.CharField(_("name"), max_length=150)
    name_ar = models.CharField(_("name (Arabic)"), max_length=150, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def display_name(self):
        """The name in the reader's language, falling back to the other when blank.

        A property rather than a choice at each display site: the second name has been stored
        since the MVP and read nowhere, which means every site that shows a department made
        the same wrong choice independently. One property makes it once.

        Falling back to `name` matters — a missing translation should degrade to a readable
        name, and an unnamed department in a dropdown is worse than an untranslated one.
        """
        from django.utils.translation import get_language

        if (get_language() or "").startswith("ar") and self.name_ar:
            return self.name_ar
        return self.name


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)

        # FR-032 (spec 004), from the staff side. One address is either a member of staff or
        # a portal customer, never both. Enforced in both managers rather than in one,
        # because a rule spanning two tables has no database constraint to fall back on and
        # whichever side is left unguarded is the side somebody uses.
        #
        # The import is local: apps.portal imports this module, and a module-level import
        # here would close the circle.
        from apps.portal.models import AddressAlreadyInUse, CustomerAccount

        if CustomerAccount.objects.filter(email__iexact=email).exists():
            raise AddressAlreadyInUse(
                f"{email} already belongs to a portal customer. Promoting a customer to staff "
                "is not an account edit — it needs the customer account closed first, so the "
                "audit trail says which of the two acted."
            )
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMINISTRATOR)
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin, TimeStampedModel):
    class Role(models.TextChoices):
        """Fixed in code and not configurable by users (MVP FR-022).

        Live chat added SUPERVISOR (FR-037): a team lead who works tickets like an Agent and
        additionally observes live conversations and coaches privately, within their own
        department. They deliberately cannot administer accounts or read the audit log —
        coaching an agent and administering the system are different jobs, and bundling them
        to get the first was the wrong trade.

        Permission checks must name the roles they ALLOW. A check phrased as "not an Agent"
        silently admits Supervisors; `test_supervisor_role.py` fails the build on that shape.
        """

        AGENT = "AGENT", _("Agent")
        SUPERVISOR = "SUPERVISOR", _("Supervisor")
        ADMINISTRATOR = "ADMINISTRATOR", _("Administrator")

    class Language(models.TextChoices):
        ARABIC = "ar", _("Arabic")
        ENGLISH = "en", _("English")

    email = models.EmailField(_("email address"), unique=True)
    full_name = models.CharField(_("full name"), max_length=200)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.AGENT)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="users", null=True
    )
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, related_name="users", null=True)
    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ARABIC)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return self.full_name or self.email

    def terminate_sessions(self):
        """FR-026: deactivation ends access immediately, not at next sign-in. Django sessions
        do not index by user, so this scans; acceptable at MVP staff-account volumes."""
        for session in Session.objects.filter(expire_date__gte=Now()):
            data = session.get_decoded()
            if str(data.get("_auth_user_id")) == str(self.pk):
                session.delete()

    def save(self, *args, **kwargs):
        was_active = None
        if self.pk:
            was_active = User.objects.filter(pk=self.pk).values_list("is_active", flat=True).first()
        super().save(*args, **kwargs)
        if was_active and not self.is_active:
            self.terminate_sessions()
            self.release_live_conversations()

    def release_live_conversations(self):
        """Hand on any live chat this account was holding (live chat FR-034, MVP FR-026).

        Here rather than in the deactivation view for the same reason `terminate_sessions` is:
        an account can be deactivated from the admin, from a shell, or from a future bulk
        action, and a customer left talking to a dismissed agent is not a failure that should
        depend on which route was taken.
        """
        from apps.chat.services.lifecycle import agent_deactivated

        agent_deactivated(self)
