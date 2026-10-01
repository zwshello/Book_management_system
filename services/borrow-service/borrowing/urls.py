from django.urls import path

from .views import BorrowDetailView, BorrowListView, BorrowReturnView, MyBorrowListView

urlpatterns = [
    path("borrows", BorrowListView.as_view()),
    path("borrows/me", MyBorrowListView.as_view()),
    path("borrows/<str:pk>", BorrowDetailView.as_view()),
    path("borrows/<str:pk>/return", BorrowReturnView.as_view()),
]
