from django.urls import path

from .internal_views import (
    AvailabilityView,
    OperationDetailView,
    ReleaseView,
    ReservationView,
)
from .summary import BookSummaryView

urlpatterns = [
    path("books/summary", BookSummaryView.as_view()),
    path("books/<str:pk>/availability", AvailabilityView.as_view()),
    path("books/<str:pk>/reservations", ReservationView.as_view()),
    path("books/<str:pk>/releases", ReleaseView.as_view()),
    path(
        "books/operations/<str:operation_key>", OperationDetailView.as_view()
    ),
]
