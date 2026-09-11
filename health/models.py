from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator


class WaterLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='water_logs')
    date = models.DateField()
    glass_count = models.PositiveIntegerField(default=0, validators=[MinValueValidator(0), MaxValueValidator(50)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('user', 'date')
        ordering = ['-date']
        indexes = [models.Index(fields=['user', '-date'])]

    def __str__(self):
        return f"WaterLog {self.user_id} {self.date}"


class WeightEntry(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='weight_entries')
    weight_kg = models.FloatField(validators=[MinValueValidator(0)])
    logged_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-logged_at']
        indexes = [models.Index(fields=['user', '-logged_at'])]

    def __str__(self):
        return f"WeightEntry {self.user_id} {self.logged_at}"
