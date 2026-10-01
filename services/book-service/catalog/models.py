import uuid

from django.db import models


class Category(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    normalized_name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "categories"
        ordering = ["name", "id"]


class Book(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "可检索"
        ARCHIVED = "ARCHIVED", "已归档"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    author = models.CharField(max_length=200)
    isbn = models.CharField(max_length=13, unique=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="books"
    )
    publisher = models.CharField(max_length=200, blank=True)
    published_date = models.DateField(null=True, blank=True)
    description = models.TextField(blank=True)
    total_copies = models.PositiveIntegerField(default=0)
    available_copies = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=8, choices=Status.choices, default=Status.ACTIVE
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "books"
        ordering = ["-created_at", "id"]
        indexes = [models.Index(fields=["category", "status"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    available_copies__lte=models.F("total_copies")
                ),
                name="books_stock_bounds",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=["ACTIVE", "ARCHIVED"]),
                name="books_valid_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(status="ACTIVE", archived_at__isnull=True)
                    | models.Q(status="ARCHIVED", archived_at__isnull=False)
                ),
                name="books_archive_consistent",
            ),
        ]


class StockOperation(models.Model):
    class Kind(models.TextChoices):
        RESERVE = "RESERVE", "预留"
        RELEASE = "RELEASE", "释放"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    operation_key = models.UUIDField(unique=True)
    borrow_id = models.UUIDField()
    book = models.ForeignKey(
        Book, on_delete=models.PROTECT, related_name="stock_operations"
    )
    kind = models.CharField(max_length=7, choices=Kind.choices)
    result = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "stock_operations"
        constraints = [
            models.UniqueConstraint(
                fields=["borrow_id", "book", "kind"],
                name="stock_borrow_book_kind_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=["RESERVE", "RELEASE"]),
                name="stock_valid_kind",
            ),
        ]
