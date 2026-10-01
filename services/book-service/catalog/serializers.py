from django.utils import timezone
from rest_framework import serializers

from .models import Book, Category
from .validators import category_name, normalize_isbn


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


class CategorySerializer(StrictFieldsMixin, serializers.ModelSerializer):
    description = serializers.CharField(
        max_length=10000, required=False, allow_blank=True
    )

    def validate_name(self, value):
        value = category_name(value)
        existing = Category.objects.filter(normalized_name=value.casefold())
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("分类名称已存在。")
        return value

    def create(self, validated_data):
        validated_data["normalized_name"] = validated_data["name"].casefold()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "name" in validated_data:
            validated_data["normalized_name"] = validated_data[
                "name"
            ].casefold()
        return super().update(instance, validated_data)

    class Meta:
        model = Category
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


class BookSerializer(StrictFieldsMixin, serializers.ModelSerializer):
    isbn = serializers.CharField(max_length=32)
    total_copies = serializers.IntegerField(
        min_value=0, max_value=2147483647, required=False
    )
    available_copies = serializers.IntegerField(
        min_value=0, max_value=2147483647, required=False
    )
    description = serializers.CharField(
        max_length=10000, required=False, allow_blank=True
    )
    category_name = serializers.CharField(
        source="category.name", read_only=True
    )

    def validate_isbn(self, value):
        value = normalize_isbn(value)
        existing = Book.objects.filter(isbn=value)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise serializers.ValidationError("ISBN 已存在，包括归档书目。")
        return value

    def validate(self, attrs):
        if self.instance is not None and (
            {"total_copies", "available_copies"} & set(attrs)
        ):
            raise serializers.ValidationError(
                "库存不能通过资料编辑修改，请使用 stock-adjustments。"
            )
        if self.instance is None:
            total = attrs.get("total_copies", 0)
            available = attrs.get("available_copies", total)
            if available > total:
                raise serializers.ValidationError(
                    {"available_copies": "可借册数不能超过总册数。"}
                )
            attrs["total_copies"] = total
            attrs["available_copies"] = available
        return attrs

    def create(self, validated_data):
        if validated_data.get("status") == Book.Status.ARCHIVED:
            validated_data["archived_at"] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if "status" in validated_data:
            validated_data["archived_at"] = (
                instance.archived_at or timezone.now()
                if validated_data["status"] == Book.Status.ARCHIVED
                else None
            )
        return super().update(instance, validated_data)

    class Meta:
        model = Book
        fields = [
            "id",
            "title",
            "author",
            "isbn",
            "category",
            "category_name",
            "publisher",
            "published_date",
            "description",
            "total_copies",
            "available_copies",
            "status",
            "created_at",
            "updated_at",
            "archived_at",
        ]
        read_only_fields = [
            "id",
            "category_name",
            "created_at",
            "updated_at",
            "archived_at",
        ]


class StockAdjustmentSerializer(StrictFieldsMixin, serializers.Serializer):
    total_copies = serializers.IntegerField(min_value=0, max_value=2147483647)


class StockRequestSerializer(StrictFieldsMixin, serializers.Serializer):
    borrow_id = serializers.UUIDField()


class BookQuerySerializer(StrictFieldsMixin, serializers.Serializer):
    title = serializers.CharField(max_length=200, required=False)
    title_exact = serializers.CharField(max_length=200, required=False)
    author = serializers.CharField(max_length=200, required=False)
    author_exact = serializers.CharField(max_length=200, required=False)
    isbn = serializers.CharField(max_length=32, required=False)
    category_id = serializers.UUIDField(required=False)
    status = serializers.ChoiceField(
        choices=Book.Status.choices, required=False
    )
    availability = serializers.ChoiceField(
        choices=["available", "unavailable"], required=False
    )
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, default=20
    )
    ordering = serializers.ChoiceField(
        choices=[
            "title",
            "-title",
            "created_at",
            "-created_at",
            "published_date",
            "-published_date",
        ],
        default="-created_at",
    )

    def validate_isbn(self, value):
        return normalize_isbn(value)


class CategoryQuerySerializer(StrictFieldsMixin, serializers.Serializer):
    name = serializers.CharField(max_length=100, required=False)
    page = serializers.IntegerField(min_value=1, default=1)
    page_size = serializers.IntegerField(
        min_value=1, max_value=100, default=20
    )
    ordering = serializers.ChoiceField(
        choices=["name", "-name", "created_at", "-created_at"], default="name"
    )
