from rest_framework import serializers
from .models import Meal, MealItem


class MealItemSerializer(serializers.ModelSerializer):
    id = serializers.SerializerMethodField()

    class Meta:
        model = MealItem
        fields = [
            'id', 'item_name', 'quantity', 'unit', 'serving_size_grams',
            'calories', 'protein_g', 'carbs_g', 'fats_g', 'fiber_g',
            'confidence', 'source'
        ]

    def get_id(self, obj):
        return str(obj.id)


class MealItemCreateSerializer(serializers.Serializer):
    item_name = serializers.CharField(min_length=1, max_length=255)
    quantity = serializers.FloatField(min_value=0.01, max_value=10000)
    unit = serializers.CharField(max_length=50, default='serving')
    serving_size_grams = serializers.FloatField(required=False, allow_null=True, min_value=0)
    calories = serializers.FloatField(min_value=0)
    protein_g = serializers.FloatField(min_value=0)
    carbs_g = serializers.FloatField(min_value=0)
    fats_g = serializers.FloatField(min_value=0)
    fiber_g = serializers.FloatField(default=0, min_value=0)
    confidence = serializers.FloatField(default=0.85, min_value=0, max_value=1)
    source = serializers.CharField(max_length=50, required=False, allow_null=True)


class MealSerializer(serializers.ModelSerializer):
    meal_id = serializers.SerializerMethodField()
    meal_items = MealItemSerializer(many=True, read_only=True)
    confidence_badge = serializers.SerializerMethodField()
    totals = serializers.SerializerMethodField()

    class Meta:
        model = Meal
        fields = [
            'meal_id', 'original_text', 'transcription_text', 'confidence_score',
            'confidence_badge', 'parsed_at', 'meal_items', 'totals', 'created_at', 'input_method',
            'meal_category'
        ]

    def get_meal_id(self, obj):
        return str(obj.id)

    def get_confidence_badge(self, obj):
        if obj.confidence_score > 0.90:
            return 'green'
        elif obj.confidence_score >= 0.70:
            return 'orange'
        else:
            return 'red'

    def get_totals(self, obj):
        items = obj.meal_items.all()
        return {
            'calories': sum(item.calories for item in items),
            'protein_g': sum(item.protein_g for item in items),
            'carbs_g': sum(item.carbs_g for item in items),
            'fats_g': sum(item.fats_g for item in items),
            'fiber_g': sum(item.fiber_g for item in items),
        }


class MealTextInputSerializer(serializers.Serializer):
    text = serializers.CharField(min_length=1, max_length=2000, trim_whitespace=True)
    category = serializers.ChoiceField(choices=Meal.MEAL_CATEGORY_CHOICES, required=False)


class MealUpdateSerializer(serializers.Serializer):
    original_text = serializers.CharField(required=False, allow_null=True)
    meal_items = MealItemCreateSerializer(many=True, min_length=1)
    meal_category = serializers.ChoiceField(choices=Meal.MEAL_CATEGORY_CHOICES, required=False)


class DashboardSerializer(serializers.Serializer):
    date = serializers.CharField()
    meals = MealSerializer(many=True)
    daily_totals = serializers.DictField()
