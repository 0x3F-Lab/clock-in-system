from django.urls import path
from . import views

app_name = "api"  # Namespace for the API app

urlpatterns = [
    path("clock-in/<int:id>/", views.clock_in, name="clock_in"),
    path("clock-out/<int:id>/", views.clock_out, name="clock_out"),
    path("list-employees/", views.list_users_name_view, name="list_users_name_view"),
    path(
        "clocked_state/<int:id>/", views.clocked_state_view, name="clocked_state_view"
    ),
    path("employees/", views.employee_details_view, name="employee_list"),
    path("employees/<int:id>/", views.employee_details_view, name="employee_detail"),
    path("raw-data-logs/", views.raw_data_logs_view, name="raw_data_logs"),
]
