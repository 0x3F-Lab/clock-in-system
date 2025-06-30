from django.urls import path
from health_safety import views

app_name = "health_safety"  # Namespace for the app

urlpatterns = [
    path(
        "manager_dashboard",
        views.manager_health_dashboard,
        name="manager_health_dashboard",
    ),
    path("dashboard", views.employee_health_dashboard, name="health_dashboard"),
]
