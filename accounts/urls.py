from django.urls import path
from . import views

urlpatterns = [
    path('register', views.RegisterView.as_view(), name='register'),
    path('login', views.LoginView.as_view(), name='login'),
    path('google', views.GoogleLoginView.as_view(), name='google_login'),
    path('me', views.MeView.as_view(), name='me'),
]
