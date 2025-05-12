from django.contrib import admin
from auth_app.models import (
    User,
    Activity,
    Store,
    StoreUserAccess,
)

# Register models
admin.site.register(User)
admin.site.register(Store)
admin.site.register(Activity)
admin.site.register(StoreUserAccess)
