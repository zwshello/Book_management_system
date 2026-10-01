"""Durable local intent plus idempotent book-service operations."""

import uuid
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from .clients import execute_stock, operation_result
from .errors import Conflict, ServiceUnavailable
from .models import BorrowRecord, BorrowerLock

COUNTED = (
    BorrowRecord.Status.PENDING,
    BorrowRecord.Status.ACTIVE,
    BorrowRecord.Status.RETURN_PENDING,
)


@transaction.atomic
def create_intent(subject, book_id, request_key, user, book, request_id):
    existing = BorrowRecord.objects.filter(request_key=request_key).first()
    if existing:
        if existing.user_id != subject or existing.book_id != book_id:
            raise Conflict("幂等编号已用于其他借阅请求。")
        return existing, False
    BorrowerLock.objects.get_or_create(user_id=subject)
    BorrowerLock.objects.select_for_update().get(user_id=subject)
    # Recheck after acquiring the user mutex. PENDING also occupies a slot.
    existing = BorrowRecord.objects.filter(request_key=request_key).first()
    if existing:
        if existing.user_id != subject or existing.book_id != book_id:
            raise Conflict("幂等编号已用于其他借阅请求。")
        return existing, False
    count = BorrowRecord.objects.filter(user_id=subject, status__in=COUNTED).count()
    if count >= settings.MAX_ACTIVE_BORROWS:
        raise Conflict("已达到同时借阅上限。")
    return (
        BorrowRecord.objects.create(
            request_key=request_key,
            user_id=subject,
            book_id=book_id,
            username_snapshot=user["username"],
            book_title_snapshot=book["title"],
            isbn_snapshot=book["isbn"],
            borrow_days=settings.BORROW_DAYS,
            last_request_id=request_id,
        ),
        True,
    )


def _save(record, *fields):
    record.save(update_fields=[*fields, "updated_at"])


@transaction.atomic
def advance(record_id, *, cancel=False):
    """One worker per record; never infer success from a timeout."""
    record = BorrowRecord.objects.select_for_update().get(pk=record_id)
    if record.status not in (
        BorrowRecord.Status.PENDING,
        BorrowRecord.Status.RETURN_PENDING,
    ):
        return record
    if cancel:
        if record.status != BorrowRecord.Status.PENDING:
            raise Conflict("仅待确认借书允许补偿取消。")
        if not record.cancel_requested:
            record.cancel_requested = True
            record.release_key = uuid.uuid4()
            _save(record, "cancel_requested", "release_key")
    kind = "RESERVE" if record.status == BorrowRecord.Status.PENDING else "RELEASE"
    try:
        outcome = operation_result(record, kind)
        if outcome is None:
            outcome = execute_stock(record, kind)
    except ServiceUnavailable:
        record.last_error_code = "DEPENDENCY_UNKNOWN"
        _save(record, "last_error_code")
        return record
    if not outcome["success"]:
        if kind == "RESERVE":
            record.status = BorrowRecord.Status.FAILED
            record.failure_code = outcome["code"]
            record.last_error_code = ""
            _save(record, "status", "failure_code", "last_error_code")
        else:
            record.last_error_code = outcome["code"]
            _save(record, "last_error_code")
        return record
    if kind == "RESERVE" and record.cancel_requested:
        try:
            release = operation_result(record, "RELEASE")
            if release is None:
                release = execute_stock(record, "RELEASE")
        except ServiceUnavailable:
            record.last_error_code = "COMPENSATION_UNKNOWN"
            _save(record, "last_error_code")
            return record
        if release["success"]:
            record.status = BorrowRecord.Status.FAILED
            record.failure_code = "CANCELLED_COMPENSATED"
            record.last_error_code = ""
            _save(record, "status", "failure_code", "last_error_code")
        else:
            record.last_error_code = release["code"]
            _save(record, "last_error_code")
        return record
    now = timezone.now()
    if kind == "RESERVE":
        record.status = BorrowRecord.Status.ACTIVE
        record.borrowed_at = now
        record.due_at = now + timedelta(days=record.borrow_days)
        record.last_error_code = ""
        _save(record, "status", "borrowed_at", "due_at", "last_error_code")
    else:
        record.status = BorrowRecord.Status.RETURNED
        record.returned_at = now
        record.last_error_code = ""
        _save(record, "status", "returned_at", "last_error_code")
    return record


@transaction.atomic
def begin_return(record_id, key, subject, *, is_admin=False):
    record = BorrowRecord.objects.select_for_update().get(pk=record_id)
    if record.user_id != subject and not is_admin:
        raise PermissionDenied("不能归还其他用户的借阅记录。")
    if record.status == BorrowRecord.Status.RETURNED:
        return record
    if record.status == BorrowRecord.Status.RETURN_PENDING:
        if record.release_key != key:
            raise Conflict("已有使用其他编号的归还请求，请核对原编号。")
        return record
    if record.status != BorrowRecord.Status.ACTIVE:
        raise Conflict("借阅当前不可归还。")
    if BorrowRecord.objects.filter(release_key=key).exists():
        raise Conflict("归还幂等编号已被使用。")
    record.status = BorrowRecord.Status.RETURN_PENDING
    record.release_key = key
    _save(record, "status", "release_key")
    return record
