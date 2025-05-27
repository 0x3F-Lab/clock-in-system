import logging
import auth_app.utils as util

from datetime import timedelta
from celery import shared_task
from django.db.models import Q
from django.utils.timezone import now, localtime
from auth_app.models import (
    User,
    Store,
    Notification,
    StoreUserAccess,
    notification_default_expires_on,
)
from clock_in_system.settings import NOTIFICATION_MAX_EXPIRY_LENGTH_DAYS


# Get the loggers
logger_celery = logging.getLogger("celery")  # For the tasks themselves
logger_beat = logging.getLogger("celery_beat")  # For the schedules (starting/stopping)


################################### SCHEDULED AUTOMATED TASKS ##############################################


@shared_task
def check_clocked_in_users():
    logger_beat.info(f"[AUTOMATED] Running task `check_clocked_in_users`.")

    try:
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

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `chceck_clocked_in_users` due to the error: {e}"
        )
        return


@shared_task
def delete_old_notifications():
    logger_beat.info(f"[AUTOMATED] Running task `delete_old_notifications`.")

    try:
        today = localtime(now()).date()
        max_age_date = today - timedelta(days=NOTIFICATION_MAX_EXPIRY_LENGTH_DAYS)

        expired_notifications = Notification.objects.filter(
            Q(expires_on__lte=today) | Q(created_at__date__lte=max_age_date)
        )

        total_count = expired_notifications.count()

        # Delete notifications (receipts will be deleted via CASCADE)
        expired_notifications.delete()

        logger_beat.info(
            f"Finished running task `delete_old_notifications` and deleted {total_count} expired notifications."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `delete_old_notifications` due to the error: {e}"
        )
        return


@shared_task
def deactivate_unassigned_users():
    logger_beat.info(f"[AUTOMATED] Running task `deactivate_unassigned_users`.")

    try:
        # Get all active users with no store associations
        unassigned_users = User.objects.filter(is_active=True).exclude(
            id__in=StoreUserAccess.objects.values_list("user_id", flat=True)
        )

        # Deactivate each user
        unassigned_users.update(is_active=False)

        logger_beat.info(
            f"Finished running task `deactivate_unassigned_users` and deactivated {unassigned_users.count()} user accounts due to missing store associations."
        )

        if unassigned_users.exists():
            logger_beat.debug(
                "The deactivated accounts are: "
                + " || ".join(
                    f"[{user.id}] {user.first_name} {user.last_name} <{user.email}>"
                    for user in unassigned_users
                )
            )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `deactivate_unassigned_users` due to the error: {e}"
        )
        return


############################################ NON-SCHEDULED AUTOMATED TASKS ########################################################################


@shared_task
def notify_managers_account_deactivated(user_id: int, manager_id: int):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_managers_account_deactivated` due to an account being deactivated by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if user.is_active:
            logger_beat.warning(
                f"Employee ID {user_id} is still active. Skipping task."
            )
            return
        elif user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return

        stores = user.get_associated_stores()  # DONT INCL INACTIVE STORES

        for store in stores:
            str_title = util.sanitise_markdown_title_text(
                f"[`{store.code}`] Employee Deactivated"
            )
            extra_note = (
                "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
                if manager.is_hidden
                else ""
            )
            str_msg = util.sanitise_markdown_message_text(
                f"Employee **<u>{user.first_name} {user.last_name}</u> _(Email: {user.email})_** has been deactivated by the manager **{manager.first_name} {manager.last_name} _(Email: {manager.email if not manager.is_hidden else 'HIDDEN'})_**"
                + extra_note
                + f"\n\nThis affects the {stores.count()} store(s) the user is connect to as they will no longer be able to login or clock in/out to any store.\nIf this is a mistake, please fix it by simply activating the account from the manager dashboard."
            )
            Notification.send_to_users(
                users=store.get_store_managers(),
                title=str_title,
                message=str_msg,
                notification_type=Notification.Type.AUTOMATIC_ALERT,
                expires_on=notification_default_expires_on(7),
            )

        logger_beat.info(
            f"Finished running task `notify_managers_account_deactivated` notified store managers for {stores.count()} store(s)."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_managers_account_deactivated` due to the error: {e}"
        )
        return


@shared_task
def notify_managers_account_activated(user_id: int, manager_id: int):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_managers_account_activated` due to an account being activated by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if not user.is_active:
            logger_beat.warning(
                f"Employee ID {user_id} is still inactive. Skipping task."
            )
            return
        elif user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return

        stores = user.get_associated_stores()  # DONT INCL INACTIVE STORES

        for store in stores:
            str_title = util.sanitise_markdown_title_text(
                f"[`{store.code}`] Employee Activated"
            )
            extra_note = (
                "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
                if manager.is_hidden
                else ""
            )
            str_msg = util.sanitise_markdown_message_text(
                f"Employee **<u>{user.first_name} {user.last_name}</u> _(Email: {user.email})_** has been activated by the manager **{manager.first_name} {manager.last_name} _(Email: {manager.email if not manager.is_hidden else 'HIDDEN'})_**"
                + extra_note
                + f"\n\nThis affects the {stores.count()} store(s) the user is connect to as they will now be able to login and clock in/out to their store(s).\nIf this is a mistake, please fix it by simply deactivating the account from the manager dashboard."
            )
            Notification.send_to_users(
                users=store.get_store_managers(),
                title=str_title,
                message=str_msg,
                notification_type=Notification.Type.AUTOMATIC_ALERT,
                expires_on=notification_default_expires_on(7),
            )

        logger_beat.info(
            f"Finished running task `notify_managers_account_activated` notified store managers for {stores.count()} store(s)."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_managers_account_activated` due to the error: {e}"
        )
        return


@shared_task
def notify_managers_and_employee_account_resigned(
    user_id: int, store_id: int, manager_id: int
):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_managers_account_resigned` due to an account being resigned from store ID '{store_id}' by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Store with ID {store_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return
        elif not store.is_active:
            logger_beat.warning(f"Store ID {store_id} is a DEACTIVATED. Skipping task.")
            return

        str_title = util.sanitise_markdown_title_text(
            f"[`{store.code}`] Employee Resigned"
        )
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
            if manager.is_hidden
            else ""
        )
        str_msg = util.sanitise_markdown_message_text(
            f"Employee **<u>{user.first_name} {user.last_name}</u> _(Email: {user.email})_** has been resigned from the store `{store.code}` by the manager "
            f"**{manager.first_name} {manager.last_name} _(Email: {manager.email if not manager.is_hidden else 'HIDDEN'})_**"
            + extra_note
            + "\n\nIf this is a mistake, please fix it by simply re-assigning the employee's existing email to the store again.\nThe employee's account or its history has not been deleted."
        )
        Notification.send_to_users(
            users=store.get_store_managers(),
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        str_title = util.sanitise_markdown_title_text(
            f"Resigned from store `{store.code}`"
        )
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins or contact the store manager(s) outside of the site.**"
            if manager.is_hidden
            else "\n\nIf this is a mistake, please contact the store manager(s) outside of the site."
        )
        str_msg = util.sanitise_markdown_message_text(
            f"Your account has been resigned from the store {store.name} (`{store.code}`) by the manager **{manager.first_name} {manager.last_name}**."
            + extra_note
        )
        Notification.send_to_users(
            users=[user],
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        logger_beat.info(
            f"Finished running task `notify_managers_account_resigned` and notified the employee and their respective store managers."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_managers_account_resigned` due to the error: {e}"
        )
        return


@shared_task
def notify_managers_and_employee_account_assigned(
    user_id: int, store_id: int, manager_id: int
):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_managers_account_assigned` due to an account being resigned from store ID '{store_id}' by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            store = Store.objects.get(id=store_id)
        except Store.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Store with ID {store_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return
        elif not store.is_active:
            logger_beat.warning(f"Store ID {store_id} is a DEACTIVATED. Skipping task.")
            return

        str_title = util.sanitise_markdown_title_text(
            f"[`{store.code}`] Employee Assigned"
        )
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
            if manager.is_hidden
            else ""
        )
        str_msg = util.sanitise_markdown_message_text(
            f"Employee **<u>{user.first_name} {user.last_name}</u> _(Email: {user.email})_** has been assigned to the store `{store.code}` by the manager **{manager.first_name} {manager.last_name} _(Email: {manager.email if not manager.is_hidden else 'HIDDEN'})_**"
            + extra_note
            + "\n\nIf this is a mistake, please fix it by simply resigning the employee from the manager dashboard."
        )
        Notification.send_to_users(
            users=store.get_store_managers(),
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        str_title = util.sanitise_markdown_title_text(
            f"Assigned to the store `{store.code}`"
        )
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins or contact the store manager(s).**"
            if manager.is_hidden
            else "\n\nIf this is a mistake, please contact the store manager(s)."
        )
        str_msg = util.sanitise_markdown_message_text(
            f"Congratulations! Your account has been assigned to the store {store.name} (`{store.code}`) by the manager **{manager.first_name} {manager.last_name}**."
            + extra_note
            + "\n\nYou can now clock in/out freely to the store."
        )
        Notification.send_to_users(
            users=[user],
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        logger_beat.info(
            f"Finished running task `notify_managers_account_assigned` and notified the employee and their respective store managers."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_managers_account_assigned` due to the error: {e}"
        )
        return


@shared_task
def notify_employee_account_reset_pin(user_id: int, manager_id: int):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_employee_account_reset_pin` due to pin reset being initiated by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return

        str_title = util.sanitise_markdown_title_text(f"Account PIN reset")
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
            if manager.is_hidden
            else ""
        )

        str_msg = util.sanitise_markdown_message_text(
            f"Your account PIN has been reset to a new random PIN by the manager **{manager.first_name} {manager.last_name}**."
            + extra_note
            + "\n\nAs your account PIN has been changed, please see your dashboard to find the new PIN.\nYou must use this new pin to manually clock in/out."
            + "\n\n_Note: Your old PIN cannot be recovered by store managers, please do not ask site admins unless necessary._"
        )
        Notification.send_to_users(
            users=[user],
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        logger_beat.info(
            f"Finished running task `notify_employee_account_reset_pin` and notified store managers."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_employee_account_reset_pin` due to the error: {e}"
        )
        return


@shared_task
def notify_employee_account_reset_password(user_id: int, manager_id: int):
    logger_beat.info(
        f"[AUTOMATED] Running task `notify_employee_account_reset_password` due to pass reset being initiated by manager ID '{manager_id}'."
    )

    try:
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Employee with ID {user_id} not found. Skipping notification task."
            )
            return

        try:
            manager = User.objects.get(id=manager_id)
        except User.DoesNotExist:
            logger_beat.critical(
                f"[FAILURE] Manager with ID {manager_id} not found. Skipping notification task."
            )
            return

        if user.is_hidden:
            logger_beat.warning(
                f"Employee ID {user_id} is a HIDDEN ACCOUNT. Skipping task."
            )
            return

        str_title = util.sanitise_markdown_title_text(f"Account Password reset")
        extra_note = (
            "\n\n**The issuing manager is a <u>SITE ADMINISTRATOR</u>, if this is wrong please send a message to the admins.**"
            if manager.is_hidden
            else ""
        )
        str_msg = util.sanitise_markdown_message_text(
            f"Your account password has been reset by the manager **{manager.first_name} {manager.last_name}**."
            + extra_note
            + "\n\nThis would have caused you to be logged out of your account and forced to re-setup your account."
            + "\nThis action has not deleted or reset any other account information or shift history. If you believe it has, please feel free to contact the site admins."
        )
        Notification.send_to_users(
            users=[user],
            title=str_title,
            message=str_msg,
            notification_type=Notification.Type.AUTOMATIC_ALERT,
            expires_on=notification_default_expires_on(7),
        )

        logger_beat.info(
            f"Finished running task `notify_employee_account_reset_password` and notified store managers."
        )

    except Exception as e:
        logger_beat.critical(
            f"[FAILURE] Failed to complete task `notify_employee_account_reset_password` due to the error: {e}"
        )
        return
