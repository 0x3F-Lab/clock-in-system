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
    Role,
    Shift,
    ShiftException,
)


# ////////////////// CREATE CUSTOM FILTERS //////////////////////////


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


# ////////////////////// CREATE CUSTOM INLINE CLASSES ///////////////////////////


class StoreUserAccessInlineForUser(admin.TabularInline):
    model = StoreUserAccess
    extra = 0
    fields = ("store", "assigned_at")
    readonly_fields = ("assigned_at",)
    verbose_name = "Associated Store"
    verbose_name_plural = "Associated Stores"

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return True


class StoreUserAccessInlineForStore(admin.TabularInline):
    model = StoreUserAccess
    extra = 0
    fields = ("user", "assigned_at")
    readonly_fields = ("assigned_at",)
    verbose_name = "Associated User"
    verbose_name_plural = "Associated Users"

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ActivityInline(admin.TabularInline):
    model = Activity
    extra = 0
    readonly_fields = (
        "login_time",
        "logout_time",
        "shift_length_mins",
        "is_public_holiday",
        "deliveries",
        "login_timestamp",
        "logout_timestamp",
        "last_updated_at",
    )
    verbose_name = "Associated Activity"
    verbose_name_plural = "Associated Activities"

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # Only limit if the parent obj exists (i.e. user is saved)
        if request.resolver_match and request.resolver_match.kwargs.get("object_id"):
            user_id = request.resolver_match.kwargs.get("object_id")
            latest_activity_ids = (
                Activity.objects.filter(employee_id=user_id)
                .order_by("-login_time")
                .values("pk")[:6]
            )
            return qs.filter(pk__in=latest_activity_ids).order_by("-login_time")
        return qs.none()


# ////////////////// REGISTER MODELS ///////////////////////


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
    inlines = [StoreUserAccessInlineForUser, ActivityInline]


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
    inlines = [StoreUserAccessInlineForStore]


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
        "store__is_active",
        "store__code",
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
        "notification__notification_type",
        "notification__recipient_group",
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


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("id", "store_code", "name", "colour_hex", "created_at")
    list_filter = ("store__code", "store__is_active", "created_at")
    search_fields = ("name", "description", "store__name", "store__code")
    ordering = ("store__code", "name")

    @admin.display(description="Store Code")
    def store_code(self, obj):
        return obj.store.code


@admin.register(Shift)
class ShiftAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store_code",
        "employee_name",
        "date",
        "start_time",
        "end_time",
        "role_display",
        "is_deleted",
        "created_at",
    )
    list_filter = (
        "is_deleted",
        "store__code",
        "role__name",
        "store__is_active",
        "employee__is_active",
        "employee__is_manager",
        "employee__is_hidden",
        "date",
    )
    search_fields = (
        "employee__first_name",
        "employee__last_name",
        "store__code",
        "store__name",
        "role__name",
    )
    ordering = ("-date", "start_time")

    @admin.display(description="Employee")
    def employee_name(self, obj):
        return f"{obj.employee.first_name} {obj.employee.last_name}"

    @admin.display(description="Store Code")
    def store_code(self, obj):
        return obj.store.code

    @admin.display(description="Role")
    def role_display(self, obj):
        return obj.role.name if obj.role else "Unassigned"


@admin.register(ShiftException)
class ShiftExceptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "store_code",
        "employee_name",
        "date",
        "reason",
        "is_approved",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "reason",
        "is_approved",
        "shift__store__code",
        "shift__store__is_active",
        "shift__employee__is_active",
        "shift__employee__is_manager",
        "shift__employee__is_hidden",
        "created_at",
    )
    search_fields = (
        "shift__employee__first_name",
        "shift__employee__last_name",
        "activity__employee__first_name",
        "activity__employee__last_name",
        "shift__store__code",
        "activity__store__code",
    )
    ordering = ("-created_at",)

    @admin.display(description="Store Code")
    def store_code(self, obj):
        try:
            return obj.get_store().code
        except Exception:
            return "N/A"

    @admin.display(description="Employee")
    def employee_name(self, obj):
        try:
            emp = obj.get_employee()
            return f"{emp.first_name} {emp.last_name}"
        except Exception:
            return "N/A"

    @admin.display(description="Date")
    def date(self, obj):
        try:
            return obj.get_date()
        except Exception:
            return "N/A"
