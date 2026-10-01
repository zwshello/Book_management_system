"""Stage 2 liveness endpoints; business routes are added later."""

from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    return JsonResponse({"service": "book-service", "stage": 4})


@require_GET
def live(request):
    return JsonResponse({"service": "book-service", "status": "live"})


urlpatterns = [
    path("api/v1/", include("catalog.urls")),
    path("internal/v1/", include("catalog.internal_urls")),
    path("", index),
    path("health/live", live),
]
