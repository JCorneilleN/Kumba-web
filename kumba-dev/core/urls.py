from django.urls import path
from .views import home, test_firestore, signup, login_view, logout_view,post_ride
from . import views


urlpatterns = [
    path('', views.login_view, name='login'),  # default landing page
    path('signup/', views.signup, name='signup'),
    path('verify/', views.verify_code, name='verify_code'),
    path('home/', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('reset-password/', views.reset_password, name='reset_password'),
]
