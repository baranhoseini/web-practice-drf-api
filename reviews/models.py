# reviews/models.py
from django.db import models
from django.conf import settings
from ads.models import Ad
from django.core.validators import MinValueValidator, MaxValueValidator


class Review(models.Model):
    ad = models.ForeignKey(Ad, on_delete=models.CASCADE, related_name="reviews")

    contractor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_received",
    )

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews_written",
    )

    text = models.TextField()
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])

    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
      return f"Review #{self.id} ({self.rating})"