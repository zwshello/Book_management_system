"""User API and liveness endpoints."""

from django.http import JsonResponse
from django.urls import include, path
from django.views.decorators.http import require_GET
from accounts.internal import AuthorizationView, EligibilityView, UserSummaryView


@require_GET
def index(request):
    return JsonResponse({"service": "user-service", "stage": 3})


@require_GET
def live(request):
    return JsonResponse({"service": "user-service", "status": "live"})


urlpatterns = [
    path("internal/v1/users/summary", UserSummaryView.as_view()),
    path("internal/v1/users/<str:pk>/authorization", AuthorizationView.as_view()),
    path("internal/v1/users/<str:pk>/eligibility", EligibilityView.as_view()),
    path("api/v1/", include("accounts.urls")),
    path("", index),
    path("health/live", live),
]
