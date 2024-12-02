from django.urls import path
from . import views

urlpatterns = [
    path(
        "", views.login_view, name="login"
    ),  # Set the login view as the default for `auth/`
    path("create/", views.create_user, name="create_user"),
    path("list/", views.user_list, name="user_list"),
    path("clock-in/", views.clock_in, name="clock_in"),
    path("clock-out/", views.clock_out, name="clock_out"),
]
