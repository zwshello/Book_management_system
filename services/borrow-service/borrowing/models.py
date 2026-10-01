import uuid

from django.db import models
from django.utils import timezone


class BorrowerLock(models.Model):
    """Only a local mutex keyed by user UUID, never a cross-service user FK."""

    user_id = models.UUIDField(primary_key=True)

    class Meta:
        db_table = "borrower_locks"


class BorrowRecord(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "借阅待核对"
        ACTIVE = "ACTIVE", "借阅中"
        RETURN_PENDING = "RETURN_PENDING", "归还待核对"
        RETURNED = "RETURNED", "已归还"
        FAILED = "FAILED", "借阅失败"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request_key = models.UUIDField(unique=True)
    user_id = models.UUIDField()
    book_id = models.UUIDField()
    username_snapshot = models.CharField(max_length=150)
    book_title_snapshot = models.CharField(max_length=200)
    isbn_snapshot = models.CharField(max_length=13)
    reservation_key = models.UUIDField(default=uuid.uuid4, unique=True)
    release_key = models.UUIDField(null=True, blank=True, unique=True)
    status = models.CharField(
        max_length=14, choices=Status.choices, default=Status.PENDING
    )
    borrowed_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    returned_at = models.DateTimeField(null=True, blank=True)
    borrow_days = models.PositiveSmallIntegerField()
    cancel_requested = models.BooleanField(default=False)
    failure_code = models.CharField(max_length=40, blank=True)
    last_error_code = models.CharField(max_length=40, blank=True)
    last_request_id = models.CharField(max_length=36, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)

    @property
    def is_overdue(self):
        return self.status == self.Status.ACTIVE and self.due_at < timezone.now()

    @property
    def display_status(self):
        return "OVERDUE" if self.is_overdue else self.status

    class Meta:
        db_table = "borrow_records"
        ordering = ["-created_at", "id"]
        indexes = [
            models.Index(fields=["user_id", "status"]),
            models.Index(fields=["book_id", "status"]),
            models.Index(fields=["status", "updated_at"]),
            models.Index(fields=["status", "due_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "PENDING",
                        "ACTIVE",
                        "RETURN_PENDING",
                        "RETURNED",
                        "FAILED",
                    ]
                ),
                name="borrow_valid_status",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        status__in=["PENDING", "FAILED"],
                        borrowed_at__isnull=True,
                        due_at__isnull=True,
                        returned_at__isnull=True,
                    )
                    | models.Q(
                        status__in=["ACTIVE", "RETURN_PENDING"],
                        borrowed_at__isnull=False,
                        due_at__isnull=False,
                        returned_at__isnull=True,
                    )
                    | models.Q(
                        status="RETURNED",
                        borrowed_at__isnull=False,
                        due_at__isnull=False,
                        returned_at__isnull=False,
                    )
                ),
                name="borrow_state_times",
            ),
            models.CheckConstraint(
                condition=models.Q(due_at__isnull=True)
                | models.Q(due_at__gt=models.F("borrowed_at")),
                name="borrow_due_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(returned_at__isnull=True)
                | models.Q(returned_at__gte=models.F("borrowed_at")),
                name="borrow_return_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(archived_at__isnull=True)
                | models.Q(status__in=["RETURNED", "FAILED"]),
                name="borrow_archive_terminal",
            ),
            models.CheckConstraint(
                condition=~models.Q(status__in=["RETURN_PENDING", "RETURNED"])
                | models.Q(release_key__isnull=False),
                name="borrow_return_has_key",
            ),
        ]
