from django.contrib import admin
from auth_app.models import User, Activity, Summary, KeyValueStore

# Register models
admin.site.register(User)
admin.site.register(Activity)
admin.site.register(Summary)
admin.site.register(KeyValueStore)
