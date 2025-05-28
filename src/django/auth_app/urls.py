from django.contrib.sitemaps.views import sitemap
from django.views.generic import TemplateView
from django.urls import path
from auth_app import views


sitemaps = {
    "static": views.StaticViewSitemap(),
}


urlpatterns = [
    path("", views.home_directory, name="home"),
    path("manifest.json", views.manifest, name="manifest"),
    path("sw.js", views.service_worker, name="service_worker"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", sitemap, {"sitemaps": sitemaps}, name="sitemap"),
    path(
        "sw.js",
        TemplateView.as_view(
            template_name="sw.js", content_type="application/javascript"
        ),
    ),
    path("offline", views.offline, name="offline"),
    path("clocking", views.employee_dashboard, name="clocking"),
    path("logout", views.logout, name="logout"),
    path("manager_dashboard", views.manager_dashboard, name="manager_dashboard"),
    path("dashboard", views.employee_dashboard, name="dashboard"),
    path("notifications", views.notification_page, name="notification_page"),
    path(
        "manage_employee_details",
        views.manage_employee_details,
        name="manage_employee_details",
    ),
    path("manage_shift_logs", views.manage_shift_logs, name="manage_shift_logs"),
    path("account_summary", views.manage_account_summary, name="account_summary"),
    path("manual_clocking", views.manual_clocking, name="manual_clocking"),
    path("dashboard", views.employee_dashboard, name="dashboard"),
    path("login", views.login, name="login"),
    path("setup", views.setup_account, name="account_setup"),
    path("schedule_dashboard", views.schedule_dashboard, name="schedule_dashboard"),
]
