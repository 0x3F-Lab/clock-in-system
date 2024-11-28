from django.urls import path
from . import views

urlpatterns = [
    path("", views.login_view, name="home"),
    path("login/", views.login_view, name="login"),
    path("manager_login/", views.manager_login, name="manager_login"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("employee_login/", views.employee_login, name="employee_login"),
    path("employee_dashboard/", views.employee_dashboard, name="employee_dashboard"),
]
