"""
The portal's identity (T014, T015).

A customer is NOT a `User`, and research.md §1 settles why by reading the middleware rather
than by preference: the deny-by-default rule is "authenticated -> let through", and `role`
defaults to AGENT. On the staff model a customer would be an agent missing a department, and
the only thing between them and the ticket queue would be that nobody had assigned them one.

Because this model does not inherit from `AbstractBaseUser`, it has no `is_authenticated`
property, no `last_login`, and no place in `AUTHENTICATION_BACKENDS`. That is the point: even
if a customer were somehow put on `request.user`, every staff view's `request.user.department`
would raise rather than quietly return `None`. Password hashing and timing-safe comparison
still come from the framework, because writing those by hand is how they get written wrong.
"""

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.core.models import TimeStampedModel


class AddressAlreadyInUse(Exception):
    """Raised when an address already belongs to a member of staff, or the reverse.

    A dedicated exception rather than IntegrityError because the two tables cannot enforce
    this between them: the database has no constraint spanning `accounts_user` and
    `portal_customeraccount`, so the rule lives in code and must be visible when it fires.
    """


def normalize(email):
    """Lowercased whole, not just the domain.

    `BaseUserManager.normalize_email` lowercases the domain and leaves the local part alone,
    which is correct by the RFC and wrong in practice: no mail provider this product will
    meet treats `Noura@` and `noura@` as different mailboxes, and leaving them distinct means
    one person can hold two accounts for one inbox and the staff/customer check in
    `create_account` can be walked around with a shift key.
    """
    return (email or "").strip().lower()


class CustomerAccountManager(models.Manager):
    def create_account(self, email, password, language=None):
        email = normalize(email)
        if not email:
            raise ValueError("A customer account needs an email address")

        # FR-032. Checked here rather than left to the database because no constraint can
        # span two tables. The window between this check and the insert is accepted: the
        # alternative is a trigger, and the realistic version of this collision is an agent
        # registering out of curiosity, not a race.
        from apps.accounts.models import User

        # `objects` includes deactivated staff on purpose. A deactivated agent is the same
        # person as the agent they were, and the ambiguity this rule exists to prevent — an
        # audit entry that cannot say which account acted — is not resolved by their leaving.
        if User.objects.filter(email__iexact=email).exists():
            raise AddressAlreadyInUse(
                f"{email} already belongs to a member of staff. One address is either staff "
                "or a customer, never both — otherwise an audit entry cannot say which acted."
            )

        account = self.model(email=email, language=language or CustomerAccount.Language.ARABIC)
        account.set_password(password)
        account.save(using=self._db)
        return account


class CustomerAccount(TimeStampedModel):
    """A person outside the organization, and nothing more than that.

    No role. No department. No branch. Not set to null — absent, so there is no field for a
    later change to populate and no column a staff scoping query could match.
    """

    class Language(models.TextChoices):
        ARABIC = "ar", _("Arabic")
        ENGLISH = "en", _("English")

    email = models.EmailField(_("email address"), unique=True)
    password = models.CharField(_("password"), max_length=128)

    #: Null until proved. Null means the account can do nothing at all — not "can do less".
    email_confirmed_at = models.DateTimeField(null=True, blank=True)

    language = models.CharField(max_length=2, choices=Language.choices, default=Language.ARABIC)
    is_active = models.BooleanField(default=True)

    objects = CustomerAccountManager()

    class Meta:
        ordering = ["email"]
        verbose_name = _("customer account")
        verbose_name_plural = _("customer accounts")

    def __str__(self):
        return self.email

    def save(self, *args, **kwargs):
        self.email = normalize(self.email)
        return super().save(*args, **kwargs)

    # --- credentials ---

    def set_password(self, raw):
        self.password = make_password(raw)

    def check_password(self, raw):
        def setter(new_hash):
            self.password = new_hash
            self.save(update_fields=["password"])

        return check_password(raw, self.password, setter)

    # --- state ---

    @property
    def is_confirmed(self):
        return self.email_confirmed_at is not None

    def confirm(self):
        self.email_confirmed_at = timezone.now()
        self.save(update_fields=["email_confirmed_at", "updated_at"])

    @property
    def may_use_the_portal(self):
        """The single condition every portal screen asks about.

        Phrased as one property so the two halves cannot drift apart. A view that checks
        `is_confirmed` and forgets `is_active` serves a deactivated customer; a view that
        checks `is_active` and forgets `is_confirmed` serves somebody who typed a stranger's
        address into a public form.
        """
        return self.is_active and self.is_confirmed


class CustomerToken(TimeStampedModel):
    """A single-use, expiring link, stored as a fingerprint rather than as itself.

    The value that goes in the email is never written down. What is stored proves a presented
    value is the right one and is useless to anyone reading the table — which matters because
    a table of unused reset links is a table of live account-takeover credentials, and the
    people who read database tables are backups, replicas and exports, not attackers.
    """

    class Purpose(models.TextChoices):
        CONFIRMATION = "CONFIRMATION", _("Confirm an email address")
        RESET = "RESET", _("Reset a password")

    account = models.ForeignKey(CustomerAccount, on_delete=models.CASCADE, related_name="tokens")
    purpose = models.CharField(max_length=20, choices=Purpose.choices)

    #: A hash of the link value, never the value.
    value_hash = models.CharField(max_length=64, db_index=True)

    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["value_hash", "purpose"])]

    def __str__(self):
        return f"{self.purpose} for {self.account_id}"

    @property
    def is_usable(self):
        return self.used_at is None and self.expires_at > timezone.now()
