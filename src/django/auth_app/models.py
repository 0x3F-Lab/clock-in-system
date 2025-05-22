import random
from datetime import timedelta
from django.db import models
from django.utils.timezone import now, localtime
from django.contrib.auth.hashers import make_password, check_password
from clock_in_system.settings import (
    NOTIFICATION_DEFAULT_EXPIRY_LENGTH_DAYS,
    NOTIFICATION_MAX_EXPIRY_LENGTH_DAYS,
)


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
        role = ""
        if self.is_hidden:
            if self.is_manager:
                role = " - MANAGER/HIDDEN"
            role = " - HIDDEN"
        elif self.is_manager:
            role = " - MANAGER"

        return f"[{self.id}] {self.first_name} {self.last_name} ({self.email}){role}"

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

    def get_associated_stores(self, show_inactive: bool = False):
        """
        Returns a queryset of all ACTIVE stores this user is associated with.
        - show_inactive: If True, includes inactive stores as well.
        """
        qs = Store.objects.filter(user_access__user=self)
        if not show_inactive:
            qs = qs.filter(is_active=True)
        return qs.distinct()

    def is_manager_of(self, employee, ignore_inactive_stores: bool = True) -> bool:
        """
        Returns True if the current user is a manager and shares at least one store with the given employee.
        Accepts a User object or ID for the employee.

        - ignore_inactive_stores: If True, only considers active shared stores. Default True.
        """
        if not self.is_manager or not self.is_active:
            return False

        # Resolve employee object if ID is provided
        if isinstance(employee, int) or (
            isinstance(employee, str) and employee.isdigit()
        ):
            try:
                employee = User.objects.get(id=int(employee))
            except User.DoesNotExist:
                return False
        elif not isinstance(employee, User):
            return False

        # Get store IDs associated with this manager
        shared_store_ids = StoreUserAccess.objects.filter(user=self).values_list(
            "store_id", flat=True
        )

        # Further filter the IDs based on the store's active state
        if ignore_inactive_stores:
            shared_store_ids = Store.objects.filter(
                id__in=shared_store_ids, is_active=True
            ).values_list("id", flat=True)

        return StoreUserAccess.objects.filter(
            user=employee, store_id__in=shared_store_ids
        ).exists()

    def get_unread_notifications(self):
        """
        Returns a queryset of unread Notifications for this user,
        ordered by newest first.
        """
        return (
            Notification.objects.filter(
                notificationreceipt__user=self,
                notificationreceipt__read_at__isnull=True,
                expires_on__gte=localtime(now()).date(),
            )
            .distinct()
            .order_by("-created_at")
        )


########################## STORES ##########################


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

    def get_store_managers(self, include_hidden=False):
        """
        Returns a queryset of ACTIVE managers who have access to the given store.
        Args:
          - include_hidden (bool) = False: Include hidden accounts (super admins) in the list.
        """
        return User.objects.filter(
            store_access__store=self,
            is_manager=True,
            is_active=True,  # Only include active users
            is_hidden=include_hidden,
        ).distinct()

    def get_clocked_in_employees(self, include_inactive=True):
        """
        Returns a queryset of users who are currently clocked in at this store.
        Ignores HIDDEN accounts.
        Args:
          - include_inactive (bool) = True: Whether to include inactive User accounts or not.
        """
        active_employee_ids = Activity.objects.filter(
            store=self, logout_time__isnull=True
        ).values_list("employee_id", flat=True)

        if include_inactive:
            return User.objects.filter(id__in=active_employee_ids, is_hidden=False)
        return User.objects.filter(
            id__in=active_employee_ids, is_hidden=False, is_active=True
        )

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
        # Prevent duplicate entries
        constraints = [
            models.UniqueConstraint(fields=["user", "store"], name="unique_user_store")
        ]

    def __str__(self):
        role = "EMPLOYEE"
        if self.user.is_hidden:
            role = "HIDDEN"
            if self.user.is_manager:
                role = "MANAGER/HIDDEN"
            role = "HIDDEN"
        elif self.user.is_manager:
            role = "MANAGER"

        return f"{self.user.first_name} {self.user.last_name} [{self.user.id}] → {self.store.code} ({role})"


########################## SHIFTS ##########################


class Activity(models.Model):
    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="activities"
    )
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
        return f"[{self.id}] [{self.login_time.date()}] {self.employee.first_name} {self.employee.last_name} ({self.employee_id}) → {self.store.code}"


########################## NOTIFICATIONS ##########################


def notification_default_expires_on(days=NOTIFICATION_DEFAULT_EXPIRY_LENGTH_DAYS):
    # Enforce maximum expiry
    days = min(days, NOTIFICATION_MAX_EXPIRY_LENGTH_DAYS)
    return (localtime(now()) + timedelta(days=days)).date()


def get_max_expiry_date():
    return (
        localtime(now()) + timedelta(days=NOTIFICATION_MAX_EXPIRY_LENGTH_DAYS)
    ).date()


class Notification(models.Model):
    class Type(models.TextChoices):
        SYSTEM_ALERT = "system_alert", "System Alert"
        AUTOMATIC_ALERT = "automatic_alert", "Automatic Alert"
        ADMIN_NOTE = "admin_note", "Admin Note"
        MANAGER_NOTE = "manager_note", "Manager Note"
        SCHEDULE_CHANGE = "schedule_change", "Schedule Change"
        GENERAL = "general", "General"
        EMERGENCY = "emergency", "Emergency"

    sender = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="sent_notifications"
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Optional: If set, limits recipients to this store",
    )
    title = models.CharField(
        max_length=200,
        null=False,
        help_text="Short subject or headline for the notification",
    )
    message = models.TextField(null=False)
    notification_type = models.CharField(
        max_length=50,
        choices=Type.choices,
        default=Type.GENERAL,
        null=False,
        help_text="The type of notification",
    )
    broadcast_to_store = models.BooleanField(
        default=False,
        help_text="If True, broadcast to all users in the store. Used only if `store` is set.",
    )
    targeted_users = models.ManyToManyField(
        User,
        related_name="notifications",
        through="NotificationReceipt",
        blank=True,
        help_text="Used when sending to specific users (USE NOTIFICATION RECEIPTS TO SET)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_on = models.DateField(
        null=True,
        blank=True,
        default=notification_default_expires_on,
        help_text="Optional expiration date after which the notification is considered inactive",
    )

    def __str__(self):
        if self.broadcast_to_store:
            return f"[{self.id}] Broadcast to {self.store.code} - {self.message[:30]}"
        return (
            f"[{self.id}] To {self.targeted_users.count()} users - {self.message[:30]}"
        )

    def mark_notification_as_read(self, user):
        receipt = NotificationReceipt.objects.filter(
            user=user, notification=self
        ).first()
        if receipt and receipt.read_at is None:
            receipt.read_at = localtime(now())
            receipt.save(update_fields=["read_at"])
        elif receipt is None:
            raise NotificationReceipt.DoesNotExist

    @classmethod
    def send_to_users(
        cls,
        users,
        title,
        message,
        notification_type=Type.GENERAL,
        sender=None,
        expires_on=None,
    ):
        """
        Create and send a notification to specific users.

        Args:
            users (iterable of User): List or queryset of User instances to receive the notification.
            title (str): Short subject or headline for the notification. MAX 200 CHARS
            message (str): Detailed message content of the notification.
            notification_type (str): One of `Notification.Type` choices defining the notification category.
            sender (User or None): Optional User instance who is sending the notification.
            expires_on (date or None): Optional expiration date for notification.
                Defaults to Notification default expiry date if None.

        Returns:
            Notification: The created Notification instance.
        """
        # Set default expiry if none set (enforce max expiry)
        if expires_on is None:
            expires_on = notification_default_expires_on()
        else:
            expires_on = min(expires_on, get_max_expiry_date())

        notif = cls.objects.create(
            sender=sender,
            title=title,
            message=message,
            notification_type=notification_type,
            expires_on=expires_on,
        )
        receipts = [
            NotificationReceipt(notification=notif, user=user) for user in users
        ]
        NotificationReceipt.objects.bulk_create(receipts)
        return notif

    @classmethod
    def send_to_store_users(
        cls,
        store,
        title,
        message,
        notification_type=Type.MANAGER_NOTE,
        sender=None,
        expires_on=None,
    ):
        """
        Create and broadcast a notification to all active users in a specific store.

        Args:
            store (Store): The Store instance to which the notification will be broadcast.
            title (str): Short subject or headline for the notification. MAX 200 CHARS
            message (str): Detailed message content of the notification.
            notification_type (str): One of `Notification.Type` choices defining the notification category.
            sender (User or None): Optional User instance who is sending the notification.
            expires_on (date or None): Optional expiration date for notification.
                Defaults to Notification default expiry date if None.

        Returns:
            Notification: The created Notification instance.
        """
        # Set default expiry if none set (enforce max expiry)
        if expires_on is None:
            expires_on = notification_default_expires_on()
        else:
            expires_on = min(expires_on, get_max_expiry_date())

        notif = cls.objects.create(
            sender=sender,
            store=store,
            title=title,
            message=message,
            notification_type=notification_type,
            broadcast_to_store=True,
            expires_on=expires_on,
        )

        # Get all active users associated with the store
        users = User.objects.filter(
            store_access__store=store, is_active=True
        ).distinct()

        receipts = [
            NotificationReceipt(notification=notif, user=user) for user in users
        ]
        NotificationReceipt.objects.bulk_create(receipts)
        return notif

    @classmethod
    def send_system_notification_to_all(
        cls, title, message, sender=None, expires_on=None
    ):
        """
        Create and broadcast a notification to all active across the whole site.

        Args:
            title (str): Short subject or headline for the notification. MAX 200 CHARS
            message (str): Detailed message content of the notification.
            sender (User or None): Optional User instance who is sending the notification.
            expires_on (date or None): Optional expiration date for notification.
                Defaults to Notification default expiry date if None.

        Returns:
            Notification: The created Notification instance.
        """
        # Set default expiry if none set (enforce max expiry)
        if expires_on is None:
            expires_on = notification_default_expires_on()
        else:
            expires_on = min(expires_on, get_max_expiry_date())

        users = User.objects.filter(is_active=True)
        return cls.send_to_users(
            users=users,
            title=title,
            message=message,
            notification_type=cls.Type.SYSTEM_ALERT,
            sender=sender,
            expires_on=expires_on,
        )


class NotificationReceipt(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="notification_receipts"
    )
    notification = models.ForeignKey(Notification, on_delete=models.CASCADE)
    read_at = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = (
            "user",
            "notification",
        )  # Ensure one receipt per user-notification

    def mark_as_read(self):
        if not self.read_at:
            self.read_at = localtime(now())
            self.save(update_fields=["read_at"])
