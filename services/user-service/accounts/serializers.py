from django.contrib.auth import password_validation
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.utils import get_md5_hash_password

from .models import User, UserManager


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("请求必须是 JSON 对象。")
        forbidden = set(data) - {
            name for name, field in self.fields.items() if not field.read_only
        }
        if forbidden:
            raise serializers.ValidationError(
                {key: "不允许提交此字段。" for key in sorted(forbidden)}
            )
        return super().to_internal_value(data)


class UserReadSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    def get_status(self, obj):
        return "ACTIVE" if obj.is_active else "DISABLED"

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "display_name",
            "role",
            "is_active",
            "status",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = fields


class UserWriteSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    username = serializers.CharField(
        min_length=3,
        max_length=150,
        validators=[UnicodeUsernameValidator()],
    )
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        min_length=8,
        max_length=128,
        trim_whitespace=False,
    )
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate_username(self, value):
        value = User.normalize_username(value)
        if len(value) < 3 or len(value) > 150:
            raise serializers.ValidationError("用户名长度必须为 3–150。")
        existing = User.objects.filter(username=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("用户名已存在。")
        return value

    def validate_email(self, value):
        value = UserManager.normalize_email(value)
        existing = User.objects.filter(email=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("邮箱已存在。")
        return value

    def validate(self, attrs):
        if "password" in attrs:
            candidate = User(
                username=attrs.get(
                    "username", getattr(self.instance, "username", "")
                ),
                email=attrs.get("email", getattr(self.instance, "email", "")),
            )
            try:
                password_validation.validate_password(
                    attrs["password"], candidate
                )
            except DjangoValidationError as error:
                raise serializers.ValidationError({"password": error.messages})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        password = validated_data.pop("password", None)
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if instance.role == User.Role.USER:
            instance.is_staff = False
            instance.is_superuser = False
        if password is not None:
            instance.set_password(password)
        instance.save()
        return instance

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "password",
            "display_name",
            "role",
            "is_active",
        ]


class RegistrationSerializer(UserWriteSerializer):
    role = None
    is_active = None

    class Meta(UserWriteSerializer.Meta):
        fields = ["username", "email", "password", "display_name"]


class ProfileSerializer(UserWriteSerializer):
    username = None
    password = None
    role = None
    is_active = None

    class Meta(UserWriteSerializer.Meta):
        fields = ["email", "display_name"]


class LoginSerializer(StrictFieldsMixin, TokenObtainPairSerializer):
    def validate(self, attrs):
        attrs["username"] = User.normalize_username(attrs["username"])
        data = super().validate(attrs)
        data["user"] = UserReadSerializer(self.user).data
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        return token


class RefreshSerializer(StrictFieldsMixin, TokenRefreshSerializer):
    def validate(self, attrs):
        token = RefreshToken(attrs["refresh"])
        try:
            user = User.objects.get(
                pk=token["sub"], is_active=True, archived_at=None
            )
        except (
            User.DoesNotExist,
            DjangoValidationError,
            ValueError,
            KeyError,
        ):
            raise AuthenticationFailed("账户已禁用、归档或不存在。")
        if token.get("hash_password") != get_md5_hash_password(user.password):
            raise AuthenticationFailed("密码已修改，请重新登录。")
        # Issue claims from current database state, never the old role claim.
        token["role"] = user.role
        attrs["refresh"] = str(token)
        return super().validate(attrs)


class LogoutSerializer(StrictFieldsMixin, serializers.Serializer):
    refresh = serializers.CharField()

    def validate_refresh(self, value):
        token = RefreshToken(value)
        if str(token["sub"]) != str(self.context["request"].user.pk):
            raise serializers.ValidationError("只能退出本人的刷新令牌。")
        return token
