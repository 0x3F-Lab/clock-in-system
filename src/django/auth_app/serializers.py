from rest_framework import serializers
from auth_app.models import Activity


class ActivitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Activity
        fields = [
            "store_id",
            "employee_id",
            "login_time",
            "logout_time",
            "shift_length_mins",
            "is_public_holiday",
            "deliveries",
            "login_timestamp",
            "logout_timestamp",
        ]

    # Override the `to_representation` method
    def to_representation(self, instance):
        # Get the original representation (dictionary) of the Activity object
        data = super().to_representation(instance)

        # Remove the 'id' field from the serialized data (if it exists)
        if "id" in data:
            del data["id"]

        # Add the 'store_id' to the serialized data (using `instance.store_id` to access the store)
        data["store_id"] = instance.store.id if instance.store else None

        return data


# Used purely for the clocked state API endpoint
class ClockedInfoSerializer(serializers.Serializer):
    employee_id = serializers.IntegerField()
    store_id = serializers.IntegerField()
    name = serializers.CharField()
    clocked_in = serializers.BooleanField()
    login_time = serializers.DateTimeField(required=False, allow_null=True)
    login_timestamp = serializers.DateTimeField(required=False, allow_null=True)
