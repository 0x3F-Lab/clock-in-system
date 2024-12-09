from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.login_view, name="home"),
    path("login/", views.login_view, name="login"),
    path("manager_login/", views.manager_login, name="manager_login"),
     path("logout/", LogoutView.as_view(next_page="/"), name="logout"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("employee_login/", views.employee_login, name="employee_login"),
    path("employee_dashboard/", views.employee_dashboard, name="employee_dashboard"),
]
