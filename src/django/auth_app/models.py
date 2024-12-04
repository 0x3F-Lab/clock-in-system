from django.db import models


class User(models.Model):
    first_name = models.CharField(max_length=100, null=False)
    last_name = models.CharField(max_length=100, null=False)
    email = models.EmailField(unique=True, null=False)
    phone_number = models.CharField(
        max_length=15, null=True
    )  # CharField to handle leading zeros
    pin = models.CharField(
        max_length=256, null=True
    )  # Store hashed pins -- Allow nullable pin for fresh account (shouldnt be used until password is set)
    password = models.CharField(
        max_length=256, null=True
    )  # Allow nullable for non-manager accounts
    birth_date = models.DateField(blank=True, default=None, null=True)
    is_active = models.BooleanField(default=False, null=False)
    is_manager = models.BooleanField(default=False, null=False)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(auto_now=True, null=False)
    clocked_in = models.BooleanField(default=False, null=False)

    def __str__(self):
        return f"[{self.id}] {self.first_name} {self.last_name} ({self.email})"


class Activity(models.Model):
    employee_id = models.ForeignKey(User, on_delete=models.CASCADE)
    login_time = models.DateTimeField(null=False)  # Rounds in time
    logout_time = models.DateTimeField(
        null=True
    )  # Nullable to allow for ongoing shifts
    shift_length_mins = models.IntegerField(default=0, null=False)
    is_public_holiday = models.BooleanField(default=False, null=False)
    deliveries = models.IntegerField(default=0, null=False)
    login_timestamp = models.DateTimeField(
        auto_now_add=True, null=False
    )  # Track the specific time
    logout_timestamp = models.DateTimeField(null=True)
    last_updated_at = models.DateTimeField(
        auto_now=True, null=False
    )  # Track modifications outside clocking

    def __str__(self):
        return f"[{self.id}] Clock-in data for {self.employee_id}"


class Summary(models.Model):
    employee_id = models.ForeignKey(User, on_delete=models.CASCADE)
    weekday_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=False, default=0.00
    )
    weekend_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=False, default=0.00
    )
    public_holiday_hours = models.DecimalField(
        max_digits=5, decimal_places=2, null=False, default=0.00
    )
    deliveries = models.IntegerField(default=0, null=False)
    summary_date = models.DateField(null=False)

    def __str__(self):
        return (
            f"[{self.id}] Weekly Summary for {self.employee_id} on {self.summary_date}"
        )
