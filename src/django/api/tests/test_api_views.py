import pytest
from rest_framework import status
from django.urls import reverse
from auth_app.models import User, Activity
from unittest.mock import patch


@pytest.mark.django_db
def test_list_users_name_success(api_client, employee):
    """
    Test successful fetching of a list of active users with their IDs and full names.
    """
    url = reverse(
        "list_users_name_view"
    )  # Adjust this to the actual URL name for list_users_name_view
    response = api_client.get(
        url,
        {
            "only_active": "true",
            "ignore_managers": "false",
            "order": "true",
            "order_by_first_name": "true",
            "clocked_in": "false",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Ensure the response is a list
    assert isinstance(data, list)

    # Check that each entry has an ID and full name
    for entry in data:
        assert isinstance(entry, list)
        assert len(entry) == 2
        assert isinstance(entry[0], int)  # ID should be an integer
        assert isinstance(entry[1], str)  # Name should be a string


@pytest.mark.django_db
def test_list_users_name_no_results(api_client):
    """
    Test when no users match the criteria (e.g., no active users).
    """
    url = reverse("list_users_name_view")
    response = api_client.get(
        url,
        {
            "only_active": "false",
            "ignore_managers": "false",
            "order": "true",
            "order_by_first_name": "true",
            "clocked_in": "false",
        },
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    data = response.json()
    assert "Error" in data
    assert data["Error"] == "No users found matching the given criteria."


@pytest.mark.django_db
def test_list_users_name_with_filters(api_client, employee, manager):
    """
    Test fetching users with specific filters, e.g., only active users and excluding managers.
    """
    url = reverse("list_users_name_view")
    response = api_client.get(
        url,
        {
            "only_active": "true",
            "ignore_managers": "true",
            "order": "true",
            "order_by_first_name": "true",
            "clocked_in": "false",
        },
    )

    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    # Ensure the manager is excluded from the results
    for entry in data:
        assert (
            entry[1] != f"{manager.first_name} {manager.last_name}"
        )  # Ensure manager is not in the list


@pytest.mark.django_db
def test_list_users_name_invalid_query_param(api_client, employee):
    """
    Test invalid query parameters.
    """
    url = reverse("list_users_name_view")
    response = api_client.get(url, {"invalid_param": "some_value"})

    assert (
        response.status_code == status.HTTP_200_OK
    )  # Expecting a 200 OK as the parameters are optional and shouldn't cause errors
    data = response.json()

    # Ensure that the data returned still contains users
    assert isinstance(data, list)
