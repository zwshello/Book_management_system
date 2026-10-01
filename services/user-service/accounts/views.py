from django.db import transaction
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

from .errors import Conflict
from .models import AdministrationLock, User
from .permissions import IsAdministrator
from .query import QuerySerializer
from .serializers import (
    LoginSerializer,
    LogoutSerializer,
    ProfileSerializer,
    RefreshSerializer,
    RegistrationSerializer,
    UserReadSerializer,
    UserWriteSerializer,
)


class RegisterView(generics.CreateAPIView):
    authentication_classes = []
    permission_classes = [AllowAny]
    serializer_class = RegistrationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(UserReadSerializer(user).data, status=201)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class RefreshView(TokenRefreshView):
    serializer_class = RefreshSerializer


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = LogoutSerializer(
            data=request.data, context={"request": request}
        )
        try:
            serializer.is_valid(raise_exception=True)
            serializer.validated_data["refresh"].blacklist()
        except TokenError as error:
            raise InvalidToken(str(error))
        return Response(status=204)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserReadSerializer(request.user).data)

    @transaction.atomic
    def patch(self, request):
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.is_active or user.archived_at is not None:
            raise PermissionDenied("账户已禁用。")
        serializer = ProfileSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(UserReadSerializer(serializer.save()).data)


def lock_administration(actor):
    AdministrationLock.objects.get_or_create(pk=1)
    AdministrationLock.objects.select_for_update().get(pk=1)
    current = User.objects.get(pk=actor.pk)
    if (
        not current.is_active
        or current.archived_at
        or current.role != User.Role.ADMIN
    ):
        raise PermissionDenied("当前账户已不具备管理员权限。")


def protect_last_administrator(user, changes, archive=False):
    losing_admin = (
        archive
        or not changes.get("is_active", user.is_active)
        or changes.get("role", user.role) != User.Role.ADMIN
    )
    if user.role == User.Role.ADMIN and user.is_active and losing_admin:
        others = User.objects.filter(
            role=User.Role.ADMIN,
            is_active=True,
            archived_at=None,
        ).exclude(pk=user.pk)
        if not others.exists():
            raise Conflict("不能停用、降级或归档最后一个有效管理员。")


class UserListView(APIView):
    permission_classes = [IsAdministrator]

    def get(self, request):
        if any(
            len(request.query_params.getlist(key)) != 1
            for key in request.query_params
        ):
            raise ValidationError("查询参数不能重复。")
        serializer = QuerySerializer(data=request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        values = serializer.validated_data
        users = User.objects.filter(archived_at=None)
        filters = (
            ("username", "username"),
            ("username_contains", "username__icontains"),
            ("role", "role"),
        )
        for key, lookup in filters:
            if key in values:
                users = users.filter(**{lookup: values[key]})
        if "is_active" in values:
            users = users.filter(is_active=values["is_active"] == "true")
        count = users.count()
        page, size = values["page"], values["page_size"]
        start = (page - 1) * size
        if page > 1 and start >= count:
            raise NotFound("页码超出范围。")
        users = users.order_by(values["ordering"], "id")[start : start + size]
        return Response(
            {
                "count": count,
                "page": page,
                "page_size": size,
                "results": UserReadSerializer(users, many=True).data,
            }
        )

    @transaction.atomic
    def post(self, request):
        lock_administration(request.user)
        serializer = UserWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(UserReadSerializer(serializer.save()).data, status=201)


class UserDetailView(generics.GenericAPIView):
    permission_classes = [IsAdministrator]
    queryset = User.objects.filter(archived_at=None)
    serializer_class = UserReadSerializer

    def get_queryset(self):
        users = super().get_queryset()
        if self.request.method in {"PATCH", "DELETE"}:
            return users.select_for_update()
        return users

    def get_object(self):
        from rest_framework.serializers import UUIDField

        UUIDField().run_validation(self.kwargs["pk"])
        return super().get_object()

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        lock_administration(request.user)
        user = self.get_object()
        serializer = UserWriteSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        protect_last_administrator(user, serializer.validated_data)
        return Response(UserReadSerializer(serializer.save()).data)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        lock_administration(request.user)
        user = self.get_object()
        protect_last_administrator(user, {}, archive=True)
        user.archived_at = timezone.now()
        user.is_active = False
        user.save(update_fields=["archived_at", "is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)
