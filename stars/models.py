from django.db import models
from django.urls import reverse


class Kid(models.Model):
    name = models.CharField(max_length=100, unique=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("stars:kid_detail", args=[self.pk])

    @property
    def balance(self):
        return self.transactions.aggregate(total=models.Sum("delta"))["total"] or 0


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
