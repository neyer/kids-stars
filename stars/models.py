import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.urls import reverse


class Kid(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)
    # Optional login for the kid. Kids can view their page and request stars,
    # but can't change balances themselves.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="kid",
    )

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("stars:kid_detail", args=[self.pk])

    @property
    def balance(self):
        return self.transactions.aggregate(total=models.Sum("delta"))["total"] or 0

    @property
    def pending_stars(self):
        """Stars the kid has asked for that a parent hasn't decided on yet."""
        return (
            self.requests.filter(status=StarRequest.PENDING).aggregate(total=models.Sum("delta"))[
                "total"
            ]
            or 0
        )


class QuickAction(models.Model):
    label = models.CharField(max_length=100)
    delta = models.IntegerField()
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]

    def __str__(self):
        sign = "+" if self.delta >= 0 else ""
        return f"{sign}{self.delta}: {self.label}"


class StarTransaction(models.Model):
    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name="transactions")
    delta = models.IntegerField()
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Bumped each time a quick-tap merges into this entry; used to decide
    # whether the next tap continues the same chunk.
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        sign = "+" if self.delta >= 0 else ""
        return f"{self.kid.name}: {sign}{self.delta} ({self.reason})"


class StarRequest(models.Model):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    STATUS_CHOICES = [(PENDING, "Pending"), (APPROVED, "Approved"), (DENIED, "Denied")]

    kid = models.ForeignKey(Kid, on_delete=models.CASCADE, related_name="requests")
    delta = models.PositiveIntegerField()
    reason = models.CharField(max_length=255)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    transaction = models.OneToOneField(
        StarTransaction, on_delete=models.SET_NULL, null=True, blank=True, related_name="request"
    )

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.kid.name}: +{self.delta} ({self.reason}) [{self.status}]"


def hash_token(key):
    return hashlib.sha256(key.encode()).hexdigest()


class ApiToken(models.Model):
    """A token another app uses to call the REST API. Only a hash of the key
    is stored; the key itself is shown once, when the token is created."""

    name = models.CharField(max_length=100, help_text="Which app uses this token")
    key_hash = models.CharField(max_length=64, unique=True, editable=False)
    prefix = models.CharField(max_length=8, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(null=True, blank=True, editable=False)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.prefix}…)"

    def set_new_key(self):
        """Gives this token a fresh key and returns it. Only its hash is kept."""
        key = secrets.token_urlsafe(32)
        self.key_hash = hash_token(key)
        self.prefix = key[:8]
        return key

    @classmethod
    def create(cls, name):
        """Returns (token, key). The key is not recoverable afterwards."""
        token = cls(name=name)
        key = token.set_new_key()
        token.save()
        return token, key
