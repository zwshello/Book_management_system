from rest_framework import serializers

from .models import BorrowRecord


class StrictFieldsMixin:
    def to_internal_value(self, data):
        if not isinstance(data, dict):
            raise serializers.ValidationError("请求必须是 JSON 对象。")
        forbidden = set(data) - {
            name for name, field in self.fields.items() if not field.read_only
        }
        if forbidden:
            raise serializers.ValidationError(
                {name: "不允许提交此字段。" for name in sorted(forbidden)}
            )
        return super().to_internal_value(data)


class BorrowCreateSerializer(StrictFieldsMixin, serializers.Serializer):
    book_id = serializers.UUIDField()


class BorrowRecordSerializer(serializers.ModelSerializer):
    display_status = serializers.CharField(read_only=True)
    is_overdue = serializers.BooleanField(read_only=True)

    class Meta:
        model = BorrowRecord
        fields = [
            "id",
            "user_id",
            "book_id",
            "username_snapshot",
            "book_title_snapshot",
            "isbn_snapshot",
            "status",
            "display_status",
            "is_overdue",
            "borrowed_at",
            "due_at",
            "returned_at",
            "borrow_days",
            "failure_code",
            "last_error_code",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = fields


class BorrowQuerySerializer(StrictFieldsMixin, serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[*BorrowRecord.Status.values, "OVERDUE"], required=False
    )
    user_id = serializers.UUIDField(required=False)
    book_id = serializers.UUIDField(required=False)
    created_from = serializers.DateField(required=False)
    created_to = serializers.DateField(required=False)
    include_archived = serializers.BooleanField(required=False, default=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, default=20)
    ordering = serializers.ChoiceField(
        choices=["created_at", "-created_at", "due_at", "-due_at"],
        default="-created_at",
    )

    def validate(self, attrs):
        if (
            attrs.get("created_from")
            and attrs.get("created_to")
            and attrs["created_from"] > attrs["created_to"]
        ):
            raise serializers.ValidationError("开始日期不得晚于结束日期。")
        return attrs


class DueDateSerializer(StrictFieldsMixin, serializers.Serializer):
    due_at = serializers.DateTimeField()
