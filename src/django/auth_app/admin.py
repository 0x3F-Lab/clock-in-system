from django.contrib import admin
from auth_app.models import User, Activity, Summary

# Register models
admin.site.register(User)
admin.site.register(Activity)
admin.site.register(Summary)
