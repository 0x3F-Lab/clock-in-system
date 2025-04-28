from django.urls import path
from auth_app import views

urlpatterns = [
    path("", views.home_directory, name="home"),
    path("clocking", views.employee_dashboard, name="clocking"),
    path("manager_login/", views.manager_login, name="manager_login"),
    path("logout/", views.logout, name="logout"),
    path("manager_dashboard/", views.manager_dashboard, name="manager_dashboard"),
    path("employee_dashboard/", views.employee_dashboard, name="employee_dashboard"),
    path(
        "manage_employee_details/",
        views.manage_employee_details,
        name="manage_employee_details",
    ),
    path("manage_shift_logs/", views.manage_shift_logs, name="manage_shift_logs"),
    # path("store_select/", views.store_select, name="store_select"),
    # path("manual_clocking/", views.manual_clocking, name="manual_clocking"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("login/", views.login, name="login"),
]
