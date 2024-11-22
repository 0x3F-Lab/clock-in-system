from django.urls import path
from . import views

urlpatterns = [
    path('', views.login_view, name='login'),  # Set the login view as the default for `auth/`
]
