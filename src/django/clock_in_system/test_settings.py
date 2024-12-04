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
