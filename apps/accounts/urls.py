from django.urls import path
from . import views

# API endpoints
urlpatterns = [
    path('register/', views.register, name='api_register'),
    path('login/', views.login_view, name='api_login'),
    path('logout/', views.logout_view, name='api_logout'),
    path('profile/', views.profile, name='api_profile'),
]