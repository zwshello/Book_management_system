from rest_framework.permissions import BasePermission, SAFE_METHODS

from .user_client import current_authorization


class CatalogPermission(BasePermission):
    message = "仅管理员可以修改图书或分类。"

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        if request.auth.get("role") != "ADMIN":
            return False
        access = request.headers["Authorization"].split()[1]
        return (
            current_authorization(request.user.id, access)["role"] == "ADMIN"
        )
