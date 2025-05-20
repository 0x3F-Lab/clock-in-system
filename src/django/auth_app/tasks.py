import logging
import auth_app.utils as util

from celery import shared_task
from django.db.models import Prefetch
from auth_app.models import (
    Store,
    Activity,
    Notification,
    notification_default_expires_on,
)


# Get the loggers
logger_celery = logging.getLogger("celery")  # For the tasks themselves
logger_beats = logging.getLogger(
    "celery_beats"
)  # For the schedules (starting/stopping)


@shared_task
def check_clocked_in_users():
    logger_beats.info(f"[AUTOMATED] Running task `chceck_clocked_in_users`.")

    total_count = 0

    for store in Store.objects.prefetch_related(
        Prefetch(
            "user_access__user__activities",
            queryset=Activity.objects.filter(logout_time__isnull=True).order_by(
                "-login_time"
            ),
            to_attr="active_activities",
        )
    ):
        print(store.code)
        clocked_in_employees = store.get_clocked_in_employees()
        print(len(clocked_in_employees))

        if not clocked_in_employees:
            continue  # Skip stores with no clocked-in employees

        # Count for logging
        total_count += len(clocked_in_employees)

        # Notify each employee individually
        for emp in clocked_in_employees:
            act = getattr(emp, "active_activities", [None])[0]

            if not act:
                logger_celery.critical(
                    f"[LATE-CLOCK-OUT] No active shift found for employee {emp.id} ({emp.first_name} {emp.last_name}) even though they appeared as clocked out for store [{store.code}]."
                )
                continue

            emp_title = util.sanitise_markdown_title_text(
                f"You forgot to clock out of store `{store.code}`"
            )
            emp_msg = util.sanitise_markdown_message_text(
                f"Our system shows you're still clocked in under the store `{store.code}`.\nYou clocked in at {act.login_time}.\n\nYour respective manager(s) have been notified.\nPlease correct this if it's a mistake."
            )
            Notification.send_to_users(
                users=[emp],
                title=emp_title,
                message=emp_msg,
                notification_type=Notification.Type.AUTOMATIC_ALERT,
                expires_on=notification_default_expires_on(7),
            )
            logger_celery.debug(
                f"[LATE-CLOCK-OUT] Sent notification to employee {emp.id} ({emp.get_full_name()})."
            )

        # Notify store managers with summary
        employee_names = "\n".join(
            f"- {emp.first_name} {emp.last_name} ({emp.email})"
            for emp in clocked_in_employees
        )
        str_title = util.sanitise_markdown_title_text(
            f"Clock-out Alert: Employees Still Clocked In [`{store.code}`]"
        )
        str_msg = util.sanitise_markdown_message_text(
            f"The following employees are still clocked in for the store `{store.code}`:\n{employee_names}\n\nThe respective employees have been notified.\nPlease correct this if it's a mistake."
        )
        Notification.send_to_users(
            users=store.get_store_managers(),
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )
        logger_celery.debug(
            f"[LATE-CLOCK-OUT] Sent manager notification for store {store.code}."
        )

    logger_celery.info(
        f"Finished running task `chceck_clocked_in_users` and found {total_count} users still clocked in. Sent message(s) to respective managers."
    )
