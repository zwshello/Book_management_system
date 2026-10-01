import secrets
import uuid
from types import SimpleNamespace

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import (
    JWTStatelessUserAuthentication,
)
from rest_framework_simplejwt.exceptions import InvalidToken

from .errors import ServiceUnavailable


class UserJWTAuthentication(JWTStatelessUserAuthentication):
    def get_user(self, validated_token):
        try:
            uuid.UUID(validated_token["sub"])
        except (KeyError, ValueError, TypeError, AttributeError):
            raise InvalidToken("JWT sub 必须为用户 UUID。")
        if validated_token.get("role") not in {"USER", "ADMIN"}:
            raise InvalidToken("JWT role 无效。")
        return super().get_user(validated_token)


class BorrowServiceAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = request.headers.get("Authorization", "").split()
        if not parts:
            return None
        expected = settings.BORROW_SERVICE_TOKEN
        if not expected or expected.startswith("CHANGE_ME"):
            raise ServiceUnavailable("借阅服务身份凭据尚未配置。")
        if (
            len(parts) != 2
            or parts[0] != "Bearer"
            or not secrets.compare_digest(parts[1].encode(), expected.encode())
        ):
            raise AuthenticationFailed("借阅服务身份凭据无效。")
        return SimpleNamespace(is_authenticated=True, service="borrow"), None

    def authenticate_header(self, request):
        return 'Bearer realm="internal-borrow"'


class StatisticsServiceAuthentication(BaseAuthentication):
    def authenticate(self, request):
        parts = request.headers.get("Authorization", "").split()
        if not parts:
            return None
        expected = settings.STATISTICS_SERVICE_TOKEN
        if not expected or expected.startswith("CHANGE_ME"):
            raise ServiceUnavailable("统计服务身份凭据尚未配置。")
        if len(parts) != 2 or parts[0] != "Bearer" or not secrets.compare_digest(parts[1].encode(), expected.encode()):
            raise AuthenticationFailed("统计服务身份凭据无效。")
        return SimpleNamespace(is_authenticated=True, service="statistics"), None

    def authenticate_header(self, request):
        return 'Bearer realm="internal-statistics"'
