from rest_framework import serializers
from auth_app.models import Activity


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "id",
            "employee_id",
            "login_time",
            "logout_time",
            "shift_length_mins",
            "is_public_holiday",
            "deliveries",
            "login_timestamp",
            "logout_timestamp",
        ]


# Used purely for the clocked state API endpoint
class ClockedInfoSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    name = serializers.CharField()
    clocked_in = serializers.BooleanField()
    login_time = serializers.DateTimeField(required=False, allow_null=True)
    login_timestamp = serializers.DateTimeField(required=False, allow_null=True)
