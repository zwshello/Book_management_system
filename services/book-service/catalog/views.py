from django.db import transaction
from django.utils import timezone
from rest_framework import generics
from rest_framework.exceptions import (
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.serializers import UUIDField
from rest_framework.views import APIView

from .errors import Conflict
from .models import Book, Category
from .permissions import CatalogPermission
from .serializers import (
    BookQuerySerializer,
    BookSerializer,
    CategoryQuerySerializer,
    CategorySerializer,
    StockAdjustmentSerializer,
)
from .user_client import current_authorization


def query_values(request, serializer_class):
    if any(
        len(request.query_params.getlist(key)) != 1
        for key in request.query_params
    ):
        raise ValidationError("查询参数不能重复。")
    serializer = serializer_class(data=request.query_params.dict())
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def page_response(queryset, values, serializer_class):
    count = queryset.count()
    page, size = values["page"], values["page_size"]
    start = (page - 1) * size
    if page > 1 and start >= count:
        raise NotFound("页码超出范围。")
    results = queryset.order_by(values["ordering"], "id")[start : start + size]
    return Response(
        {
            "count": count,
            "page": page,
            "page_size": size,
            "results": serializer_class(results, many=True).data,
        }
    )


def is_admin(request):
    return request.auth.get("role") == "ADMIN"


class CategoryListView(APIView):
    permission_classes = [CatalogPermission]

    def get(self, request):
        values = query_values(request, CategoryQuerySerializer)
        categories = Category.objects.all()
        if "name" in values:
            categories = categories.filter(name__icontains=values["name"])
        return page_response(categories, values, CategorySerializer)

    @transaction.atomic
    def post(self, request):
        serializer = CategorySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=201)


class UUIDDetailMixin:
    def get_object(self):
        UUIDField().run_validation(self.kwargs["pk"])
        return super().get_object()

    def get_queryset(self):
        objects = super().get_queryset()
        if self.request.method in {"PATCH", "DELETE", "POST"}:
            return objects.select_for_update()
        return objects


class CategoryDetailView(UUIDDetailMixin, generics.GenericAPIView):
    permission_classes = [CatalogPermission]
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        category = self.get_object()
        if category.books.exists():
            raise Conflict("分类仍被图书引用，请先迁移图书分类。")
        category.delete()
        return Response(status=204)


def lock_category(category):
    try:
        return Category.objects.select_for_update().get(pk=category.pk)
    except Category.DoesNotExist:
        raise ValidationError({"category": "分类不存在。"})


class BookListView(APIView):
    permission_classes = [CatalogPermission]

    def get(self, request):
        values = query_values(request, BookQuerySerializer)
        books = Book.objects.select_related("category")
        status = values.get("status", Book.Status.ACTIVE)
        if status == Book.Status.ARCHIVED and not is_admin(request):
            raise PermissionDenied("普通用户不能查询归档图书。")
        if status == Book.Status.ARCHIVED:
            access = request.headers["Authorization"].split()[1]
            if (
                current_authorization(request.user.id, access)["role"]
                != "ADMIN"
            ):
                raise PermissionDenied("当前账户不是管理员。")
        books = books.filter(status=status)
        filters = {
            "title": "title__icontains",
            "title_exact": "title__iexact",
            "author": "author__icontains",
            "author_exact": "author__iexact",
            "isbn": "isbn",
            "category_id": "category_id",
        }
        for key, lookup in filters.items():
            if key in values:
                books = books.filter(**{lookup: values[key]})
        if "availability" in values:
            if values["availability"] == "available":
                books = books.filter(
                    status=Book.Status.ACTIVE, available_copies__gt=0
                )
            else:
                books = books.exclude(
                    status=Book.Status.ACTIVE, available_copies__gt=0
                )
        return page_response(books, values, BookSerializer)

    @transaction.atomic
    def post(self, request):
        serializer = BookSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            category=lock_category(serializer.validated_data["category"])
        )
        return Response(serializer.data, status=201)


class BookDetailView(UUIDDetailMixin, generics.GenericAPIView):
    permission_classes = [CatalogPermission]
    queryset = Book.objects.select_related("category")
    serializer_class = BookSerializer

    def get_queryset(self):
        books = super().get_queryset()
        if self.request.method == "GET":
            books = books.filter(status=Book.Status.ACTIVE)
        return books

    def get(self, request, *args, **kwargs):
        return Response(self.get_serializer(self.get_object()).data)

    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        extras = {}
        if "category" in serializer.validated_data:
            extras["category"] = lock_category(
                serializer.validated_data["category"]
            )
        serializer.save(**extras)
        return Response(serializer.data)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        book = self.get_object()
        book.status = Book.Status.ARCHIVED
        book.archived_at = book.archived_at or timezone.now()
        book.save(update_fields=["status", "archived_at", "updated_at"])
        return Response(status=204)


class StockAdjustmentView(UUIDDetailMixin, generics.GenericAPIView):
    permission_classes = [CatalogPermission]
    queryset = Book.objects.all()
    serializer_class = StockAdjustmentSerializer

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        book = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        total = serializer.validated_data["total_copies"]
        occupied = book.total_copies - book.available_copies
        if total < occupied:
            raise Conflict("新总册数不能低于已占用册数。")
        book.total_copies = total
        book.available_copies = total - occupied
        book.save(
            update_fields=["total_copies", "available_copies", "updated_at"]
        )
        return Response(BookSerializer(book).data)
