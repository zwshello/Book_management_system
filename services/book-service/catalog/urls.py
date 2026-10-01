from django.urls import path

from .views import (
    BookDetailView,
    BookListView,
    CategoryDetailView,
    CategoryListView,
    StockAdjustmentView,
)

urlpatterns = [
    path("categories", CategoryListView.as_view()),
    path("categories/<str:pk>", CategoryDetailView.as_view()),
    path("books", BookListView.as_view()),
    path("books/<str:pk>/stock-adjustments", StockAdjustmentView.as_view()),
    path("books/<str:pk>", BookDetailView.as_view()),
]
