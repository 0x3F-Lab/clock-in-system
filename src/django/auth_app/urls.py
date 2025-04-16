from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path("", views.employee_dashboard, name="home"),
    path("manager_login/", views.manager_login, name="manager_login"),
    path("logout/", views.logout_view, name="logout"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("employee_dashboard/", views.employee_dashboard, name="employee_dashboard"),
    path(
        "manage_employee_details/",
        views.manage_employee_details,
        name="manage_employee_details",
    ),
    path("manage_shift_logs/", views.manage_shift_logs, name="manage_shift_logs"),
]
