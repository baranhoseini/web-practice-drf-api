from django.conf import settings
from django.db import models


class Ad(models.Model):
    class Status(models.TextChoices):
        OPEN = "OPEN", "Open"
        ASSIGNED = "ASSIGNED", "Assigned"
        DONE = "DONE", "Done"
        CANCELED = "CANCELED", "Canceled"

    title = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=100)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPEN)

    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ads")

    assigned_contractor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_ads",
    )

    contractor_marked_done = models.BooleanField(default=False)

    scheduled_at = models.DateTimeField(null=True, blank=True)
    location = models.CharField(max_length=255, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.status})"


class WorkRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        ACCEPTED = "ACCEPTED", "Accepted"
        REJECTED = "REJECTED", "Rejected"
        CANCELED = "CANCELED", "Canceled"

    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="requests")
    contractor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="work_requests")
    message = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("ad", "contractor")

    def __str__(self):
        return f"Request({self.ad_id}->{self.contractor_id}) [{self.status}]"
