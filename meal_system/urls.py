from django.urls import path, include
from django.views.generic import TemplateView
from django.conf import settings

urlpatterns = [
    # API routes
    path('auth/', include('accounts.urls')),
    path('meals/', include('meals.urls')),
    path('health/', include('health.urls')),

    # Template routes
    path('login', TemplateView.as_view(template_name='login.html'), name='login'),
    path('register', TemplateView.as_view(template_name='register.html'), name='register'),
    path('', TemplateView.as_view(template_name='dashboard.html'), name='dashboard'),
]

# Provide Google Client ID to templates
if not hasattr(settings, '_TEMPLATE_CONTEXT_PROCESSORS_ADDED'):
    from django.template.context_processors import csrf

    def google_client_id(request):
        return {'google_client_id': settings.GOOGLE_CLIENT_ID}

    settings.TEMPLATES[0]['OPTIONS']['context_processors'].append('meal_system.urls.google_client_id')
    settings._TEMPLATE_CONTEXT_PROCESSORS_ADDED = True
