import secrets

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import UUIDField
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError

from .models import User


class BookServiceIdentity:
    is_authenticated = True


class InvalidServiceCredential(AuthenticationFailed):
    api_code = "INVALID_SERVICE_CREDENTIAL"


class BookServiceAuthentication(BaseAuthentication):
    credential_settings = ("BOOK_SERVICE_TOKEN",)

    def authenticate(self, request):
        parts = request.headers.get("Authorization", "").split()
        if not parts:
            return None
        expected = [getattr(settings, key, "") for key in self.credential_settings]
        expected = [
            value for value in expected if value and not value.startswith("CHANGE_ME")
        ]
        if not expected:
            from rest_framework.exceptions import APIException

            error = APIException("服务身份凭据尚未配置。")
            error.status_code = 503
            raise error
        if (
            len(parts) != 2
            or parts[0] != "Bearer"
            or not any(
                secrets.compare_digest(parts[1].encode(), value.encode())
                for value in expected
            )
        ):
            raise InvalidServiceCredential("服务身份凭据无效。")
        return BookServiceIdentity(), None

    def authenticate_header(self, request):
        return 'Bearer realm="internal-book"'


class BorrowServiceAuthentication(BookServiceAuthentication):
    credential_settings = ("BORROW_SERVICE_TOKEN",)

    def authenticate_header(self, request):
        return 'Bearer realm="internal-borrow"'


class AuthorizedServiceAuthentication(BookServiceAuthentication):
    credential_settings = ("BOOK_SERVICE_TOKEN", "BORROW_SERVICE_TOKEN", "STATISTICS_SERVICE_TOKEN")


class StatisticsServiceAuthentication(BookServiceAuthentication):
    credential_settings = ("STATISTICS_SERVICE_TOKEN",)

    def authenticate_header(self, request):
        return 'Bearer realm="internal-statistics"'


def presented_user(request, pk, *, missing_not_found=False):
    subject = UUIDField().run_validation(pk)
    raw = request.headers.get("X-User-Access-Token", "")
    if not raw:
        raise AuthenticationFailed("必须提交用户 access token。")
    authentication = JWTAuthentication()
    try:
        token = authentication.get_validated_token(raw.encode())
        if str(token.get("sub")) != str(subject):
            raise PermissionDenied("用户与令牌主体不一致。")
        if missing_not_found and not User.objects.filter(pk=subject).exists():
            raise NotFound("用户不存在。")
        user = authentication.get_user(token)
    except TokenError as error:
        raise InvalidToken(str(error))
    if user.archived_at is not None:
        raise AuthenticationFailed("账户已归档。")
    return user


class AuthorizationView(APIView):
    """Book service confirms a presented user access token against current DB."""

    authentication_classes = [AuthorizedServiceAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = presented_user(request, pk)
        return Response(
            {
                "id": str(user.pk),
                "role": user.role,
                "is_active": user.is_active,
                "archived_at": None,
            }
        )


class EligibilityView(APIView):
    """Borrow service checks a signed actor and current account before intent."""

    authentication_classes = [BorrowServiceAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user = presented_user(request, pk, missing_not_found=True)
        return Response(
            {
                "id": str(user.pk),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "can_borrow": True,
            }
        )


class UserSummaryView(APIView):
    authentication_classes = [StatisticsServiceAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.query_params:
            from rest_framework.exceptions import ValidationError

            raise ValidationError("此接口不接受查询参数。")
        users = User.objects.filter(archived_at__isnull=True)
        return Response({"total_users": users.count()})
