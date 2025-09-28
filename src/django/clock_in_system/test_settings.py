from .settings import *

###################################################################
#                                                                 #
#     THIS CONFIG IS PURELY FOR TESTING PURPOSES (pytest)!!       #
#                                                                 #
#     It must be an exact copy of the regular settings only       #
#     with a modified database (in-memory) for testing.           #
#                                                                 #
###################################################################


# Override the DATABASES setting for testing
DATABASES["default"] = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": ":memory:",  # Use an in-memory SQLite database
}

# Use cache for session storage in testing
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Override the Cache setting for testing
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "default_django_cache",
    },
    "holiday_checks": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "holiday_checks_cache",
    },
    "user_stats": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "user_stats_cache",
    },
}

# Override logging settings
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] [{module}] {asctime}: {message}",
            "style": "{",
        },
        "simple": {
            "format": "[{levelname}] {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "INFO",  # Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "DEBUG",  # Minimum level this logger will process
            "propagate": False,
        },
        "api": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "auth_app": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "celery": {  # Celery-specific logger
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery_beat": {  # Celery Beat-specific logger
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "middleware": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
    "root": {  # Root logger for broader debugging
        "handlers": ["console"],
        "level": "DEBUG",
    },
}
