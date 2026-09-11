from datetime import date, datetime
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone

from .models import WaterLog, WeightEntry
from .serializers import WaterLogSerializer, WeightEntrySerializer, WaterLogCreateUpdateSerializer, WeightEntryCreateSerializer


class WaterLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get('date')
        if not date_str:
            target_date = date.today()
        else:
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response({'detail': 'date must be YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)

        water_log = WaterLog.objects.filter(user=request.user, date=target_date).first()
        if not water_log:
            return Response({'glass_count': 0, 'date': target_date.isoformat()}, status=status.HTTP_200_OK)

        serializer = WaterLogSerializer(water_log)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WaterLogCreateUpdateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        target_date = serializer.validated_data.get('date') or date.today()
        glass_count = serializer.validated_data['glass_count']

        water_log, created = WaterLog.objects.update_or_create(
            user=request.user,
            date=target_date,
            defaults={'glass_count': glass_count}
        )

        response_serializer = WaterLogSerializer(water_log)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class WeightLogView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            limit = int(request.query_params.get('limit', 10))
        except (ValueError, TypeError):
            limit = 10
        limit = max(1, min(limit, 100))

        entries = WeightEntry.objects.filter(user=request.user).order_by('-logged_at')[:limit]
        serializer = WeightEntrySerializer(entries, many=True)
        return Response({'entries': serializer.data}, status=status.HTTP_200_OK)

    def post(self, request):
        serializer = WeightEntryCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response({'detail': serializer.errors}, status=status.HTTP_400_BAD_REQUEST)

        weight_kg = serializer.validated_data['weight_kg']
        logged_at = serializer.validated_data.get('logged_at') or timezone.now()

        entry = WeightEntry.objects.create(
            user=request.user,
            weight_kg=weight_kg,
            logged_at=logged_at
        )

        response_serializer = WeightEntrySerializer(entry)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)
