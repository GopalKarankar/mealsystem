from django.urls import path
from . import views

urlpatterns = [
    path('voice', views.CreateMealVoiceView.as_view(), name='create_meal_voice'),
    path('text', views.CreateMealTextView.as_view(), name='create_meal_text'),
    path('image', views.CreateMealImageView.as_view(), name='create_meal_image'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
    path('', views.ListMealsView.as_view(), name='list_meals'),
    path('<str:meal_id>', views.MealDetailView.as_view(), name='meal_detail'),
]
