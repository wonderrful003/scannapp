from django.urls import path
from .views import index, health, ScanView

urlpatterns = [
    path('',             index,            name='index'),
    path('api/scan/',    ScanView.as_view(), name='scan'),
    path('api/health/',  health,           name='health'),
]
