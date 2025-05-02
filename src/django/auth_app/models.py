import random
from django.db import models
from django.contrib.auth.hashers import make_password, check_password


class User(models.Model):
    first_name = models.CharField(max_length=100, null=False)
    last_name = models.CharField(max_length=100, null=False)
    email = models.EmailField(unique=True, null=False)
    phone_number = models.CharField(
        max_length=15, null=True, blank=True
    )  # CharField to handle leading zeros
    pin = models.CharField(max_length=6, unique=True, null=True)
    password = models.CharField(
        max_length=256, null=True
    )  # Allow nullable for non-setup accounts
    birth_date = models.DateField(blank=True, default=None, null=True)
    is_active = models.BooleanField(default=False, null=False)
    is_manager = models.BooleanField(default=False, null=False)
    is_hidden = models.BooleanField(
        default=False, null=False
    )  # Used for admin accounts (completely hidden from manager menus)
    is_setup = models.BooleanField(
        default=False, null=False
    )  # Used to determine if an account needs to be setup (set/reset their password)
    created_at = models.DateTimeField(auto_now_add=True, null=False)
    updated_at = models.DateTimeField(auto_now=True, null=False)

    def __str__(self):
        return f"[{self.id}] {self.first_name} {self.last_name} ({self.email})"

    # Password management
    def set_password(self, raw_password: str) -> None:
        """
        Sets the user's password by hashing it.
        """
        self.password = make_password(raw_password)
        self.save(update_fields=["password"])

    def check_password(self, raw_password: str) -> bool:
        """
        Checks if the provided password matches the stored hashed password.
        """
        if not self.password:
            return False
        return check_password(raw_password, self.password)

    # Pin management
    def set_unique_pin(self):
        """
        Assign a unique 6-digit pin to the user.
        """
        pin = f"{random.randint(0, 999999):06}"  # Format to always generate a 6-digit string
        while User.objects.filter(pin=pin).exists():  # Check if the pin already exists
            pin = f"{random.randint(0, 999999):06}"  # If it does, generate a new one
        self.pin = pin

    def check_pin(self, pin: str) -> bool:
        """
        Checks if the provided pin matches the stored hashed pin.
        """
        if not self.pin:
            return False
        return self.pin == pin

    def is_clocked_in(self, store=None) -> bool:
        """
        Returns True if the user is currently clocked in.
        If a store is provided (Store object or ID), it checks for that store only.
        If no store is given, checks across all associated stores.
        """
        active_activities = Activity.objects.filter(
            employee=self,
            logout_time__isnull=True,
        )

        if store:
            if isinstance(store, int) or (isinstance(store, str) and store.isdigit()):
                active_activities = active_activities.filter(store_id=int(store))
            elif isinstance(store, Store):
                active_activities = active_activities.filter(store=store)

        return active_activities.exists()

    def get_last_active_activity_for_store(self, store):
        """
        Returns the current active (ongoing) Activity for this user limited to the provided store.
        Provide 'store' as the Store object or its ID.
        Returns None if no active activity exists.
        """
        activities = Activity.objects.filter(employee=self, logout_time__isnull=True)

        # Filter by store
        if isinstance(store, int) or (isinstance(store, str) and store.isdigit()):
            activities = activities.filter(store_id=int(store))
        elif isinstance(store, Store):
            activities = activities.filter(store=store)

        return activities.last()  # Returns None if no match

    def is_associated_with_store(self, store) -> bool:
        """
        Checks if the user is associated with the given store (either way).
        You can pass a store object or store id.
        """
        if isinstance(store, Store):  # Check if store is an object
            return StoreUserAccess.objects.filter(user=self, store=store).exists()
        elif isinstance(store, int) or (
            isinstance(store, str) and store.isdigit()
        ):  # If store is an ID
            return StoreUserAccess.objects.filter(
                user=self, store_id=int(store)
            ).exists()
        return False

    def get_associated_stores(self):
        """
        Returns a queryset of all ACTIVE stores this user is associated with.
        """
        return Store.objects.filter(user_access__user=self, is_active=True).distinct()

    def is_manager_of(self, employee) -> bool:
        """
        Returns True if the current user is a manager and shares at least one store with the given employee.
        Accepts a User object or ID for the employee.
        """
        if not self.is_manager or not self.is_active:
            return False

        if isinstance(employee, int) or (
            isinstance(employee, str) and employee.isdigit()
        ):
            try:
                employee = User.objects.get(id=int(employee))
            except User.DoesNotExist:
                return False
        elif not isinstance(employee, User):
            return False

        shared_store_ids = StoreUserAccess.objects.filter(user=self).values_list(
            "store_id", flat=True
        )

        return StoreUserAccess.objects.filter(
            user=employee, store_id__in=shared_store_ids
        ).exists()


class Store(models.Model):
    name = models.CharField(unique=True, max_length=250, null=False)
    code = models.CharField(
        unique=True, max_length=10, null=False
    )  # 4-10 character unique store code (i.e. GRNWDPZA)
    location_street = models.CharField(max_length=255, null=True)
    location_latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=False
    )  # Float (max 7 decimal places)
    location_longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=False
    )
    allowable_clocking_dist_m = models.PositiveIntegerField(
        null=False, default=500, help_text="Allowed clock-in distance in meters"
    )
    store_pin = models.CharField(max_length=255, unique=True, null=False)
    is_active = models.BooleanField(default=False, null=False)
    updated_at = models.DateTimeField(auto_now=True, null=False)

    def __str__(self):
        return f"[{self.id}] {self.code} - {self.name}"

    def set_code(self, code):
        if not code:
            raise ValueError("Unique store code must be provided.")

        code = code.strip().upper()
        if (len(code) < 4) or (len(code) > 10):
            raise ValueError("Unique store code must be 4-10 characters long.")

        self.code = code
        self.save()

    def get_store_managers(self):
        """
        Returns a queryset of ACTIVE managers who have access to the given store.
        """
        return User.objects.filter(
            store_access__store=self,
            is_manager=True,
            is_active=True,  # Only include active users
        ).distinct()

    def is_associated_with_user(self, user):
        """
        Checks if the store is associated with the given user (either way).
        You can pass a user object or user id.
        """
        if isinstance(user, User):
            return StoreUserAccess.objects.filter(store=self, user=user).exists()
        elif isinstance(user, int) or (isinstance(user, str) and user.isdigit()):
            return StoreUserAccess.objects.filter(
                store=self, user_id=int(user)
            ).exists()
        return False


class StoreUserAccess(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="store_access"
    )
    store = models.ForeignKey(
        Store, on_delete=models.CASCADE, related_name="user_access"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "store")  # Prevent duplicate entries

    def __str__(self):
        role = "Manager" if self.user.is_manager else "Employee"
        return f"{self.user} → {self.store} ({role})"


class Activity(models.Model):
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    store = models.ForeignKey(Store, on_delete=models.CASCADE, default=1)
    login_time = models.DateTimeField(null=False)  # Rounds in time
    logout_time = models.DateTimeField(
        null=True
    )  # Nullable to allow for ongoing shifts
    shift_length_mins = models.IntegerField(default=0, null=False)
    is_public_holiday = models.BooleanField(default=False, null=False)
    deliveries = models.IntegerField(default=0, null=False)
    login_timestamp = models.DateTimeField(null=True)
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


class KeyValueStore(models.Model):
    key = models.CharField(max_length=255, unique=True)
    value = models.CharField(max_length=256, null=False)

    def __str__(self):
        return f"{self.key}: {self.value}"
