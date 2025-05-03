from django.urls import path
from . import views

app_name = "api"  # Namespace for the API app

urlpatterns = [
    path("clock-in/", views.clock_in, name="clock_in"),
    path("clock-out/", views.clock_out, name="clock_out"),
    path("clocked-state/", views.clocked_state_view, name="clocked_state"),
    path("list-recent-shifts/", views.list_recent_shifts, name="list_recent_shifts"),
    path(
        "list-account-summaries/",
        views.list_account_summaries,
        name="list_account_summaries",
    ),
    path(
        "modify-account-password/",
        views.modify_account_password,
        name="modify_account_password",
    ),
    # JSON API endpoint for weekly summary data
    path("weekly-summary/", views.weekly_summary_view, name="weekly_summary_view"),
    # HTML page that uses JS to fetch from the above API
    path("weekly-summary-page/", views.weekly_summary_page, name="weekly_summary_page"),
    path("reset-summary/", views.reset_summary_view, name="reset_summary_view"),
    path(
        "list-store-employee-names/",
        views.list_store_employee_names,
        name="list_store_employee_names",
    ),
    path(
        "list-employee-details/",
        views.list_all_employee_details,
        name="list_all_employee_details",
    ),
    path(
        "list-employee-details/<int:id>/",
        views.list_singular_employee_details,
        name="list_singular_employee_details",
    ),
    path(
        "modify-account-information/<int:id>/",
        views.modify_account_information,
        name="modify_other_account_information",
    ),
    path(
        "modify-account-information/",
        views.modify_account_information,
        name="modify_account_information",
    ),
    path("create-employee/", views.create_new_employee, name="create_new_employee"),
    path(
        "modify-account-status/<int:id>/",
        views.modify_account_status,
        name="modify_account_status",
    ),
    path(
        "list-shift-details/",
        views.list_all_shift_details,
        name="list_all_shift_details",
    ),
    path(
        "list-shift-details/<int:id>/",
        views.list_singular_shift_details,
        name="list_singular_shift_details",
    ),
    path(
        "update-shift-details/<int:id>/",
        views.update_shift_details,
        name="update_shift_details",
    ),
    path("create-shift/", views.create_new_shift, name="create_new_shift"),
    path(
        "list-associated-stores/",
        views.list_associated_stores,
        name="list_associated_stores",
    ),
]
