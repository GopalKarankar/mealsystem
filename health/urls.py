from django.urls import path
from . import views

urlpatterns = [
    path('water', views.WaterLogView.as_view(), name='water_log'),
    path('weight', views.WeightLogView.as_view(), name='weight_log'),
]
