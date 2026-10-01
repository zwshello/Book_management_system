from django.db import transaction
from rest_framework.exceptions import NotFound

from .errors import Conflict
from .models import Book, StockOperation


@transaction.atomic
def operate(book_id, borrow_id, operation_key, kind):
    try:
        book = Book.objects.select_for_update().get(pk=book_id)
    except Book.DoesNotExist:
        raise NotFound("图书不存在。")
    existing = StockOperation.objects.filter(
        operation_key=operation_key
    ).first()
    if existing:
        if (
            existing.book_id != book.pk
            or existing.borrow_id != borrow_id
            or existing.kind != kind
        ):
            raise Conflict("幂等编号与原请求不一致。")
        return existing
    if StockOperation.objects.filter(
        book=book, borrow_id=borrow_id, kind=kind
    ).exists():
        raise Conflict("该借阅操作已使用其他编号，请核对原操作。")
    code = None
    if kind == StockOperation.Kind.RESERVE:
        if book.status != Book.Status.ACTIVE:
            code = "BOOK_ARCHIVED"
        elif book.available_copies == 0:
            code = "OUT_OF_STOCK"
        else:
            book.available_copies -= 1
    else:
        reservation = StockOperation.objects.filter(
            book=book, borrow_id=borrow_id, kind=StockOperation.Kind.RESERVE
        ).first()
        if not reservation or not reservation.result["success"]:
            code = "RESERVATION_NOT_FOUND"
        elif book.available_copies >= book.total_copies:
            code = "STOCK_CONFLICT"
        else:
            book.available_copies += 1
    if code is None:
        book.save(update_fields=["available_copies", "updated_at"])
    result = {
        "success": code is None,
        "code": code or "OK",
        "operation_key": str(operation_key),
        "borrow_id": str(borrow_id),
        "book_id": str(book.pk),
        "kind": kind,
        "total_copies": book.total_copies,
        "available_copies": book.available_copies,
    }
    return StockOperation.objects.create(
        operation_key=operation_key,
        borrow_id=borrow_id,
        book=book,
        kind=kind,
        result=result,
    )
