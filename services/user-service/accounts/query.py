from rest_framework import serializers

from .models import User
from .serializers import StrictFieldsMixin


class QuerySerializer(StrictFieldsMixin, serializers.Serializer):
    username = serializers.CharField(max_length=150, required=False)
    username_contains = serializers.CharField(max_length=150, required=False)
    role = serializers.ChoiceField(choices=User.Role.choices, required=False)
    is_active = serializers.ChoiceField(
        choices=["true", "false"], required=False
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, default=20
    )
    ordering = serializers.ChoiceField(
        choices=["username", "-username", "created_at", "-created_at"],
        default="-created_at",
    )

    def validate_username(self, value):
        return User.normalize_username(value)
