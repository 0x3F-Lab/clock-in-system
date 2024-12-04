from rest_framework import serializers
from auth_app.models import User, Activity, Summary


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "id",
            "employee_id",
            "login_time",
            "logout_time",
            "is_public_holiday",
            "deliveries",
        ]


class SummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Summary
        fields = [
            "id",
            "employee_id",
            "weekday_hours",
            "weekend_hours",
            "public_holiday_hours",
            "deliveries",
            "summary_date",
        ]
