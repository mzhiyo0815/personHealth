from django.urls import URLResolver


def test_health_endpoint(client):
    response = client.get("/health/")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_app_urlconfs_are_included():
    from config.urls import urlpatterns

    included_routes = {
        str(pattern.pattern)
        for pattern in urlpatterns
        if isinstance(pattern, URLResolver)
    }

    assert {"", "accounts/"} <= included_routes
