from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('api/fatigue/', views.api_fatigue, name='api_fatigue'),
    path('api/logs/', views.api_logs, name='api_logs'),
    path('api/recovery/', views.api_recovery, name='api_recovery'),
    path('api/environment/', views.api_environment, name='api_environment'),
    path('api/daily_report/', views.api_daily_report, name='api_daily_report'),
    path('api/settings/', views.api_settings, name='api_settings'),
]
