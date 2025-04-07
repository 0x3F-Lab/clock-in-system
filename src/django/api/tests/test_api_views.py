import pytest
from rest_framework import status
from django.urls import reverse
from auth_app.models import User, Activity
from unittest.mock import patch

@pytest.fixture
def manager(db):
    
    # Generate user with manager permisions 
    return User.objects.create(
        first_name="Manager",
        last_name="McBoss",
        email="manager@example.com",
        is_active=True,
        is_manager=True,
        password="testpassword123", 
    )

@pytest.mark.django_db
def test_list_users_name_success(api_client, employee):
    """
    Test successful fetching of a list of active users with their IDs and full names.
    """

    api_client.force_authenticate(user=manager) # Forcefully auth as Manager to bypass missing authentication

    url = reverse("api:list_users_name_view")
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

    api_client.force_authenticate(user=manager) # Forcefully auth as Manager to bypass missing authentication
    
    url = reverse("api:list_users_name_view")
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
    api_client.force_authenticate(user=manager) # Forcefully auth as Manager to bypass missing authentication

    url = reverse("api:list_users_name_view")
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

    api_client.force_authenticate(user=manager) # Forcefully auth as Manager to bypass missing authentication

    url = reverse("api:list_users_name_view")
    response = api_client.get(url, {"invalid_param": "some_value"})

    assert (
        response.status_code == status.HTTP_200_OK
    )  # Expecting a 200 OK as the parameters are optional and shouldn't cause errors
    data = response.json()

    # Ensure that the data returned still contains users
    assert isinstance(data, list)


@pytest.mark.django_db
def test_clocked_state_view_success(api_client, employee):
    """
    Test the clocked_state_view for an employee who is not clocked in.
    """
    url = reverse("api:clocked_state_view", args=[employee.id])
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == employee.id
    assert data["name"] == f"{employee.first_name} {employee.last_name}"
    assert data["clocked_in"] is False


@pytest.mark.django_db
def test_clocked_state_view_clocked_in_success(api_client, clocked_in_employee):
    """
    Test the clocked_state_view for an employee who is clocked in.
    """
    url = reverse("api:clocked_state_view", args=[clocked_in_employee.id])
    response = api_client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["employee_id"] == clocked_in_employee.id
    assert (
        data["name"]
        == f"{clocked_in_employee.first_name} {clocked_in_employee.last_name}"
    )
    assert data["clocked_in"] is True
    assert "login_time" in data
    assert "login_timestamp" in data


@pytest.mark.django_db
def test_clocked_state_view_user_not_found(api_client):
    """
    Test the clocked_state_view for a non-existent employee.
    """
    url = reverse("api:clocked_state_view", args=[999])
    response = api_client.get(url)

    assert response.status_code == 404
    data = response.json()
    assert data["Error"] == "User not found with ID 999."


@pytest.mark.django_db
def test_clocked_state_view_bugged_state(api_client, employee):
    """
    Test the clocked_state_view for an employee with a bugged state (no activity record).
    """
    # Mark employee as clocked in without an activity record
    employee.clocked_in = True
    employee.save()

    url = reverse("api:clocked_state_view", args=[employee.id])
    response = api_client.get(url)

    assert response.status_code == 417
    data = response.json()
    assert (
        data["Error"]
        == "User state is bugged due to missing activity records. Please contact an admin."
    )
