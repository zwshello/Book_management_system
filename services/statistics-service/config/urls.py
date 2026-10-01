"""Statistics API and liveness endpoints."""

from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    return JsonResponse({"service": "statistics-service", "stage": 6})


@require_GET
def live(request):
    return JsonResponse({"service": "statistics-service", "status": "live"})


urlpatterns = [
    path("api/v1/", include("analytics.urls")),
    path("", index),
    path("health/live", live),
]
