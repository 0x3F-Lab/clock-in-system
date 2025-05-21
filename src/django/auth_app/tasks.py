import logging
import auth_app.utils as util

from celery import shared_task
from auth_app.models import Store, Notification, notification_default_expires_on


# Get the loggers
logger_celery = logging.getLogger("celery")  # For the tasks themselves
logger_beat = logging.getLogger("celery_beat")  # For the schedules (starting/stopping)


@shared_task
def check_clocked_in_users():
    logger_beat.info(f"[AUTOMATED] Running task `check_clocked_in_users`.")

    total_count = 0

    for store in Store.objects.filter(is_active=True).all():
        clocked_in_employees = store.get_clocked_in_employees(include_inactive=True)

        if not clocked_in_employees:
            continue  # Skip stores with no clocked-in employees

        # Count for logging
        total_count += len(clocked_in_employees)

        # Notify each employee individually
        for emp in clocked_in_employees:
            emp_title = util.sanitise_markdown_title_text(
                f"You forgot to clock out of store `{store.code}`"
            )
            emp_msg = util.sanitise_markdown_message_text(
                f"Our system shows you're still clocked in under the store `{store.code}`.\nYour respective manager(s) have been notified.\n\nPlease correct this if it's a mistake."
            )
            Notification.send_to_users(
                users=[emp],
                title=emp_title,
                message=emp_msg,
                notification_type=Notification.Type.AUTOMATIC_ALERT,
                expires_on=notification_default_expires_on(7),
            )
            logger_beat.debug(
                f"[LATE-CLOCK-OUT] Sent notification to employee ID {emp.id} ({emp.first_name} {emp.last_name}) for Store {store.code}."
            )

        # Notify store managers with summary
        employee_names = "\n".join(
            f"<li>{emp.first_name} {emp.last_name} ({emp.email}){' [INACTIVE ACCOUNT]' if not emp.is_active else ''}</li>"
            for emp in clocked_in_employees
        )
        str_title = util.sanitise_markdown_title_text(
            f"[`{store.code}`] Clock-out Alert: Employees Still Clocked In"
        )
        str_msg = util.sanitise_markdown_message_text(
            f"The following employees are still clocked in for the store `{store.code}`:\n<ul>{employee_names}</ul>\n\nThe respective employees have been notified.\nPlease correct this if it's a mistake."
        )
        Notification.send_to_users(
            users=store.get_store_managers(),
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )
        logger_beat.debug(
            f"[LATE-CLOCK-OUT] Sent manager notification for store {store.code}."
        )

    logger_beat.info(
        f"Finished running task `chceck_clocked_in_users` and found {total_count} users still clocked in. Sent message(s) to respective managers."
    )
