from django.urls import path
from .views import home, test_firestore, signup, login_view, logout_view,post_ride


urlpatterns = [
    path('', home, name='home'),
    path('test/', test_firestore, name='test'),
    path('signup/', signup, name='signup'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
]
urlpatterns += [
    path('post/', post_ride, name='post_ride'),
]

