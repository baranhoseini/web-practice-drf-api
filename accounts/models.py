
from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER = "CUSTOMER", "Customer"
        CONTRACTOR = "CONTRACTOR", "Contractor"
        SUPPORT = "SUPPORT", "Support"
        ADMIN = "ADMIN", "Admin"

    phone = models.CharField(max_length=20, unique=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    def __str__(self):
        return self.username or self.email or f"user:{self.pk}"
