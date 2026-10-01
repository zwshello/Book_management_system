from rest_framework.permissions import BasePermission

from .models import User


class IsAdministrator(BasePermission):
    message = "仅管理员可以访问此接口。"

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user.is_authenticated
            and user.is_active
            and user.archived_at is None
            and user.role == User.Role.ADMIN
        )
