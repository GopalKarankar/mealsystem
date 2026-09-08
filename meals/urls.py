from django.urls import path
from . import views

urlpatterns = [
    path('voice', views.CreateMealVoiceView.as_view(), name='create_meal_voice'),
    path('', views.ListMealsView.as_view(), name='list_meals'),
    path('<str:meal_id>', views.UpdateMealView.as_view(), name='update_meal'),
    path('<str:meal_id>', views.DeleteMealView.as_view(), name='delete_meal'),
]

dashboard_urlpatterns = [
    path('dashboard', views.DashboardView.as_view(), name='dashboard'),
]

urlpatterns += dashboard_urlpatterns
