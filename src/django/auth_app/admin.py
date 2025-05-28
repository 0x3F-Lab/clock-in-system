from django.contrib import admin
from django.utils.timezone import now, localtime
from django.utils.translation import gettext_lazy as _
from auth_app.models import (
    User,
    Activity,
    Store,
    StoreUserAccess,
    Notification,
    NotificationReceipt,
)


# Custom filter lists
class ShiftStatusFilter(admin.SimpleListFilter):
    title = _("Shift Status")
    parameter_name = "shift_status"

    def lookups(self, request, model_admin):
        return (
            ("finished", _("Finished")),
            ("ongoing", _("Ongoing (No Logout)")),
        )

    def queryset(self, request, queryset):
        if self.value() == "finished":
            return queryset.exclude(logout_time__isnull=True)
        if self.value() == "ongoing":
            return queryset.filter(logout_time__isnull=True)
        return queryset


class ExpiryStatusFilter(admin.SimpleListFilter):
    title = "Expired"
    parameter_name = "expired"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Expired"),
            ("no", "Not Expired"),
        )

    def queryset(self, request, queryset):
        now_time = localtime(now())

        if self.value() == "yes":
            return queryset.filter(expires_on__lt=now_time)
        elif self.value() == "no":
            return queryset.filter(expires_on__gte=now_time)
        return queryset


# Register models WITH CUSTOM COLUMNS
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "email",
        "is_setup",
        "is_active",
        "is_manager",
        "is_hidden",
        "created_at",
    )
    list_filter = ("is_setup", "is_active", "is_manager", "is_hidden")
    search_fields = ("first_name", "last_name", "email", "pin")
    ordering = ("last_name", "first_name")


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "code",
        "name",
        "store_pin",
        "is_active",
        "allowable_clocking_dist_m",
    )
    list_filter = ("is_active",)
    search_fields = ("code", "name", "store_pin")
    ordering = ("name",)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee",
        "store_code",
        "login_time",
        "logout_time",
        "shift_length_mins",
        "deliveries",
        "is_public_holiday",
    )
    list_filter = ("is_public_holiday", "store__code", ShiftStatusFilter)
    search_fields = ("employee__first_name", "employee__last_name", "employee__email")
    ordering = ("-login_time",)

    @admin.display(description="Store Code")
    def store_code(self, obj):
        return obj.store.code


@admin.register(StoreUserAccess)
class StoreUserAccessAdmin(admin.ModelAdmin):
    list_display = ("id", "user_full_name", "store_code", "role", "assigned_at")
    search_fields = (
        "user__first_name",
        "user__last_name",
        "store__name",
        "store__code",
    )
    list_filter = (
        "user__is_active",
        "user__is_manager",
        "user__is_hidden",
        "user__is_setup",
        "store__code",
        "store__is_active",
    )
    ordering = ("-assigned_at",)

    @admin.display(description="User Full Name")
    def user_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    @admin.display(description="Store Code")
    def store_code(self, obj):
        return obj.store.code

    @admin.display(description="Role")
    def role(self, obj):
        if obj.user.is_hidden:
            if obj.user.is_manager:
                return "Manager/Hidden"
            return "Hidden"
        elif obj.user.is_manager:
            return "Manager"
        return "Employee"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "notification_type",
        "sender",
        "recipient_group",
        "recipient_count",
        "store_code",
        "created_at",
        "expires_on",
    )
    list_filter = (
        "notification_type",
        "recipient_group",
        "store__code",
        ExpiryStatusFilter,
    )
    search_fields = ("title", "message", "sender__email")
    ordering = ("-created_at",)

    @admin.display(description="Store Code")
    def store_code(self, obj):
        if obj.store is None:
            return None
        else:
            return obj.store.code

    @admin.display(description="Recipient Count")
    def recipient_count(self, obj):
        return obj.targeted_users.count()


@admin.register(NotificationReceipt)
class NotificationReceiptAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "notification", "read_at", "received_at")
    list_filter = (
        "read_at",
        "user__is_setup",
        "user__is_active",
        "user__is_manager",
        "user__is_hidden",
    )
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "notification__title",
    )
    ordering = ("-received_at",)
