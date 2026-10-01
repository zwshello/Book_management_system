"""Borrow API and liveness endpoints."""

from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET
from borrowing.internal_statistics import BorrowSummaryView


@require_GET
def index(request):
    return JsonResponse({"service": "borrow-service", "stage": 5})


@require_GET
def live(request):
    return JsonResponse({"service": "borrow-service", "status": "live"})


urlpatterns = [
    path("internal/v1/borrows/summary", BorrowSummaryView.as_view()),
    path("api/v1/", include("borrowing.urls")),
    path("", index),
    path("health/live", live),
]
