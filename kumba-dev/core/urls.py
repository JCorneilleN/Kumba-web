from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),     # “/” → login
    path('signup/', views.signup, name='signup'),
    path('verify/', views.verify_code, name='verify_code'),
    path('home/', views.home, name='home'),
    path('logout/', views.logout_view, name='logout'),
    path('reset-password/', views.reset_password, name='reset_password'),
    path('post-ride/', views.post_ride, name='post_ride'),
    path('rides/', views.list_rides, name='list_rides'),
    path('rides/<str:ride_id>/join/', views.join_ride, name='join_ride'),
    path('rides/<str:ride_id>/request/', views.request_join, name='request_join'),
    path('rides/<str:ride_id>/requests/', views.ride_requests, name='ride_requests'),
    path('rides/<str:ride_id>/requests/<str:user_id>/<str:action>/', views.handle_request, name='handle_request'),

]

