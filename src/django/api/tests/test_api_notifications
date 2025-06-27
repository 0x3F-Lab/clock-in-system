import pytest
from django.urls import reverse
from auth_app.models import Notification


@pytest.mark.django_db
def test_mark_notification_read(
    logged_in_employee, employee, clocked_in_employee, notification_all
):
    """
    Test that a notification can be marked as "read" individually by the user without affecting other users.
    """
    api_client = logged_in_employee

    # Check users have the notification
    assert employee.get_unread_notifications().count() == 1
    assert clocked_in_employee.get_unread_notifications().count() == 1

    url = reverse("api:mark_notification_read", args=[notification_all.id])
    response = api_client.post(url)

    assert response.status_code == 202
    data = response.json()
    assert data["notification_id"] == notification_all.id

    # Check notification marked as read for that user only
    assert employee.get_unread_notifications().count() == 0
    assert clocked_in_employee.get_unread_notifications().count() == 1


@pytest.mark.django_db
def test_send_individual_manager_notification(
    logged_in_manager,
    employee,
    manager,
    store,
    store_associate_employee,
    store_associate_manager,
):
    """
    Test that a individual manager notification can be sent from manager -> user
    """
    api_client = logged_in_manager

    # Check user doesnt have any notification
    assert employee.get_unread_notifications().count() == 0
    assert manager.get_unread_notifications().count() == 0

    title = "Important Manager Message"
    message = "This notification is a important message from your manager"

    url = reverse("api:send_employee_message", args=[employee.id])
    response = api_client.post(
        url,
        {
            "title": title,
            "message": message,
            "notification_type": "manager_note",
        },
    )

    assert response.status_code == 201
    data = response.json()
    assert data["employee_name"] == employee.first_name

    # Check notification marked as read for that user only
    assert employee.get_unread_notifications().count() == 1
    assert manager.get_unread_notifications().count() == 0

    # Assert notification saved correctly
    notif = Notification.objects.get(id=int(data["notification_id"]))
    assert notif is not None
    assert notif.title == title
    assert message in notif.message  # Message gets parsed and encased with <p></p> tags
    assert notif.sender == manager
    assert notif.notification_type == "manager_note"


@pytest.mark.django_db
def test_send_manager_message_to_unrelated_employee(
    logged_in_manager, employee, manager, store, store_associate_manager
):
    """
    Test that a manager message cant be sent to an unrelated user.
    """
    api_client = logged_in_manager

    # Check user doesnt have any notification
    assert employee.get_unread_notifications().count() == 0
    assert manager.get_unread_notifications().count() == 0

    title = "Important Manager Message"
    message = "This notification is a important message from your manager"

    url = reverse("api:send_employee_message", args=[employee.id])
    response = api_client.post(
        url,
        {
            "title": title,
            "message": message,
            "notification_type": "manager_note",
        },
    )

    assert response.status_code == 403
    assert (
        "Not authorised to send a message to an unassociated employee."
        in response.json()["Error"]
    )


@pytest.mark.django_db
def test_individual_manager_notification_type_authorisation(
    logged_in_manager,
    employee,
    manager,
    store,
    store_associate_employee,
    store_associate_manager,
):
    """
    Test that a normal manager cannot access admin_note, system_alert or automatic_alert notification types.
    """
    api_client = logged_in_manager

    title = "Important Manager Message"
    message = "This notification is a important message from your manager"

    url = reverse("api:send_employee_message", args=[employee.id])
    response = api_client.post(
        url,
        {
            "title": title,
            "message": message,
            "notification_type": "admin_note",
        },
    )

    assert response.status_code == 403
    assert "Not authorised" in response.json()["Error"]

    response = api_client.post(
        url,
        {
            "title": title,
            "message": message,
            "notification_type": "system_alert",
        },
    )

    assert response.status_code == 403
    assert "Not authorised" in response.json()["Error"]

    response = api_client.post(
        url,
        {
            "title": title,
            "message": message,
            "notification_type": "automatic_alert",
        },
    )

    assert response.status_code == 403
    assert "Not authorised" in response.json()["Error"]
