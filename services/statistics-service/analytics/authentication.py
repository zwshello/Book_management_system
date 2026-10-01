import uuid

from rest_framework_simplejwt.authentication import JWTStatelessUserAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken


class UserJWTAuthentication(JWTStatelessUserAuthentication):
    def get_user(self, validated_token):
        try:
            uuid.UUID(validated_token["sub"])
        except (KeyError, ValueError, TypeError, AttributeError):
            raise InvalidToken("JWT sub 必须为用户 UUID。")
        if validated_token.get("role") not in {"USER", "ADMIN"}:
            raise InvalidToken("JWT role 无效。")
        return super().get_user(validated_token)
