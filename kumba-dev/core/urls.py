from django.urls import path
from .views import home, test_firestore

urlpatterns = [
    path('', home, name='home'),
    path('test/', test_firestore, name='test'),
]

