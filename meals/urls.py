from django.urls import path
from . import views

urlpatterns = [
    path('voice', views.CreateMealVoiceView.as_view(), name='create_meal_voice'),
    path('voice/preview', views.CreateMealVoicePreviewView.as_view(), name='create_meal_voice_preview'),
    path('text', views.CreateMealTextView.as_view(), name='create_meal_text'),
    path('text/preview', views.CreateMealTextPreviewView.as_view(), name='create_meal_text_preview'),
    path('image', views.CreateMealImageView.as_view(), name='create_meal_image'),
    path('image/preview', views.CreateMealImagePreviewView.as_view(), name='create_meal_image_preview'),
    path('confirm', views.ConfirmMealView.as_view(), name='confirm_meal'),
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
    path('', views.ListMealsView.as_view(), name='list_meals'),
    path('<str:meal_id>', views.MealDetailView.as_view(), name='meal_detail'),
]
