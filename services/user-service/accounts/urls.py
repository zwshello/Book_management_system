from django.urls import path

from .views import (
    LoginView,
    LogoutView,
    ProfileView,
    RefreshView,
    RegisterView,
    UserDetailView,
    UserListView,
)

urlpatterns = [
    path("auth/register", RegisterView.as_view()),
    path("auth/login", LoginView.as_view()),
    path("auth/refresh", RefreshView.as_view()),
    path("auth/logout", LogoutView.as_view()),
    path("users/me", ProfileView.as_view()),
    path("users", UserListView.as_view()),
    path("users/<str:pk>", UserDetailView.as_view()),
]
