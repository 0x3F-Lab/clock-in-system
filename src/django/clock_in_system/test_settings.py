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
    },
    "root": {  # Root logger for broader debugging
        "handlers": ["console"],
        "level": "DEBUG",
    },
}
