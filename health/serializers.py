from rest_framework import serializers
from .models import WaterLog, WeightEntry


class WaterLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterLog
        fields = ['id', 'date', 'glass_count', 'created_at', 'updated_at']


class WeightEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = WeightEntry
        fields = ['id', 'weight_kg', 'logged_at', 'created_at', 'updated_at']


class WaterLogCreateUpdateSerializer(serializers.Serializer):
    date = serializers.DateField(required=False)
    glass_count = serializers.IntegerField(min_value=0, max_value=50)


class WeightEntryCreateSerializer(serializers.Serializer):
    weight_kg = serializers.FloatField(min_value=0)
    logged_at = serializers.DateTimeField(required=False)
