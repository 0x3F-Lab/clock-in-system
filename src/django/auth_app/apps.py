from django.apps import AppConfig


class AuthAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "auth_app"

    def ready(self):
        # Trigger signal registration
        import auth_app.signals
