from django.urls import path
from .views import home, test_firestore

urlpatterns = [
    path('', home),  # Root URL
    path('test/', test_firestore),
]

