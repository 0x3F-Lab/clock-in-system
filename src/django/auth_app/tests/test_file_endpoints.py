import pytest
from django.urls import reverse
from clock_in_system.settings import STATIC_CACHE_VER


@pytest.mark.django_db
def test_service_worker(client):
    """
    Test that the service worker JavaScript file is returned with the correct content type and context.
    """
    url = reverse("service_worker")
    response = client.get(url)

    # Check if the status code is 200 (OK)
    assert response.status_code == 200

    # Check if the correct content type is returned
    assert response["Content-Type"] == "application/javascript"

    # Check that the response contains the variables required
    assert f'suffix: "{STATIC_CACHE_VER}"' in response.content.decode()
    assert "BASE_URL" in response.content.decode()
    assert "STATIC_URL" in response.content.decode()
    assert "OFFLINE_URL" in response.content.decode()


@pytest.mark.django_db
def test_manifest(client):
    """
    Test that the manifest JSON file is returned with the correct content type and context.
    """
    url = reverse("manifest")
    response = client.get(url)

    # Check if the status code is 200 (OK)
    assert response.status_code == 200

    # Check if the correct content type is returned
    assert response["Content-Type"] == "application/manifest+json"

    # Check that the response contains the variables required
    assert "scope" in response.content.decode()
    assert "id" in response.content.decode()
    assert "short_name" in response.content.decode()
    assert "name" in response.content.decode()


@pytest.mark.django_db
def test_service_worker_cache_control(client):
    """
    Test that the service worker has the correct cache control headers.
    """
    url = reverse("service_worker")
    response = client.get(url)

    # Check for cache control headers
    assert response["Cache-Control"] == "no-cache, must-revalidate, no-store"


@pytest.mark.django_db
def test_manifest_cache_control(client):
    """
    Test that the manifest has the correct cache control headers.
    """
    url = reverse("manifest")
    response = client.get(url)

    # Check for cache control headers
    assert response["Cache-Control"] == "no-cache, must-revalidate, no-store"
