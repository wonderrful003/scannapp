from django.urls import path
from .views import index, health, ScanView, debug_scan

urlpatterns = [
    path('',             index,             name='index'),
    path('api/scan/',    ScanView.as_view(), name='scan'),
    path('api/health/',  health,            name='health'),
    path('api/debug/',   debug_scan,        name='debug'),
]
