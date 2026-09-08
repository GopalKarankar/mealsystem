from django.db import models
from django.conf import settings


class Meal(models.Model):
    INPUT_METHOD_CHOICES = [('voice', 'Voice'), ('text', 'Text'), ('image', 'Image')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='meals')
    original_text = models.TextField()
    transcription_text = models.TextField(null=True, blank=True)
    parsed_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    confidence_score = models.FloatField(default=0.85)
    input_method = models.CharField(max_length=10, choices=INPUT_METHOD_CHOICES, default='voice')

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f"Meal {self.id} - {self.user.username}"


class MealItem(models.Model):
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE, related_name='meal_items')
    item_name = models.CharField(max_length=255)
    quantity = models.FloatField()
    unit = models.CharField(max_length=50, default='serving')
    serving_size_grams = models.FloatField(null=True, blank=True)
    calories = models.FloatField()
    protein_g = models.FloatField()
    carbs_g = models.FloatField()
    fats_g = models.FloatField()
    fiber_g = models.FloatField(default=0)
    confidence = models.FloatField(default=0.85)
    source = models.CharField(max_length=50, default='llm_estimate')
    llm_generated = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.item_name} ({self.meal.id})"
