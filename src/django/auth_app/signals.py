import logging
from django.dispatch import receiver
from django.db.models.signals import pre_delete
from auth_app.models import ShiftException, Shift, Activity


logger = logging.getLogger("auth_app")


# UPON DELETING BOTH RELATED SHIFT (ROSTER) AND ACTIVITY (ACTUAL SHIFT) IT WILL DELETE THE RELATED EXCEPTION #
@receiver(pre_delete, sender=Shift)
def cleanup_shift_exceptions(sender, instance, **kwargs):
    try:
        exc = ShiftException.objects.get(shift=instance)
        if not exc.activity:
            logger.debug(
                f"[DELETE: SHIFTEXCEPTION (ID: {exc.id})] [SIGNAL-SHIFT-DEL] Shift ID: {instance.id} -- Reason: {exc.reason.upper()} -- Approved: {'Yes' if exc.is_approved else 'No'}"
            )
            exc.delete()
        else:
            exc.shift = None
            exc.save()
    except ShiftException.DoesNotExist:
        pass
    except Exception as e:
        logger.warning(
            f"Failed to cleanup the related ShiftException after deleting a shift, producing error: {str(e)}"
        )


@receiver(pre_delete, sender=Activity)
def cleanup_activity_exceptions(sender, instance, **kwargs):
    try:
        exc = ShiftException.objects.get(activity=instance)
        if not exc.shift:
            logger.debug(
                f"[DELETE: SHIFTEXCEPTION (ID: {exc.id})] [SIGNAL-ACTIVITY-DEL] Activity ID: {instance.id} -- Reason: {exc.reason.upper()} -- Approved: {'Yes' if exc.is_approved else 'No'}"
            )
            exc.delete()
        else:
            exc.activity = None
            exc.save()
    except ShiftException.DoesNotExist:
        pass
    except Exception as e:
        logger.warning(
            f"Failed to cleanup the related ShiftException after deleting an activity, producing error: {str(e)}"
        )
