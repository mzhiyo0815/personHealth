from django.http import JsonResponse
from django.urls import include, path

urlpatterns = [
    path("health/", lambda request: JsonResponse({"status": "ok"})),
    path("accounts/", include("accounts.urls")),
    path("", include("tracker.urls")),
]
