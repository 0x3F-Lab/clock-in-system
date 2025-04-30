from django.urls import path
from auth_app import views

urlpatterns = [
    path("", views.home_directory, name="home"),
    path("clocking", views.employee_dashboard, name="clocking"),
    path("logout/", views.logout, name="logout"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("dashboard/", views.employee_dashboard, name="dashboard"),
    path(
        "manage_employee_details/",
        views.manage_employee_details,
        name="manage_employee_details",
    ),
    path("manage_shift_logs/", views.manage_shift_logs, name="manage_shift_logs"),
    path("manual_clocking/", views.manual_clocking, name="manual_clocking"),
    path("dashboard/", views.employee_dashboard, name="dashboard"),
    path("login/", views.login, name="login"),
]
