from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.serializers import UUIDField
from rest_framework.views import APIView

from .clients import book_availability, user_eligibility
from .errors import Conflict
from .models import BorrowRecord
from .serializers import (
    BorrowCreateSerializer,
    BorrowQuerySerializer,
    BorrowRecordSerializer,
    DueDateSerializer,
)
from .workflow import advance, begin_return, create_intent


def subject(request):
    return UUIDField().run_validation(str(request.user.id))


def access(request):
    return request.headers["Authorization"].split()[1]


def current_admin(request):
    if request.auth.get("role") != "ADMIN":
        raise PermissionDenied("需要管理员权限。")
    account = user_eligibility(subject(request), access(request))
    if account["role"] != "ADMIN":
        raise PermissionDenied("当前账户不是管理员。")
    return account


def key_header(request):
    raw = request.headers.get("Idempotency-Key", "")
    return UUIDField().run_validation(raw)


def validate_id(pk):
    return UUIDField().run_validation(pk)


def record_or_404(pk):
    try:
        return BorrowRecord.objects.get(pk=validate_id(pk))
    except BorrowRecord.DoesNotExist:
        raise NotFound("借阅记录不存在。")


def record_response(record, *, created=False):
    if record.status in (
        BorrowRecord.Status.PENDING,
        BorrowRecord.Status.RETURN_PENDING,
    ):
        return Response(BorrowRecordSerializer(record).data, status=202)
    if record.status == BorrowRecord.Status.FAILED:
        error = Conflict({"record": BorrowRecordSerializer(record).data})
        error.api_code = record.failure_code or "BORROW_FAILED"
        if record.failure_code == "BOOK_NOT_FOUND":
            raise NotFound("图书不存在。")
        raise error
    return Response(
        BorrowRecordSerializer(record).data,
        status=201 if created and record.status == BorrowRecord.Status.ACTIVE else 200,
    )


def query_values(request):
    if any(
        len(request.query_params.getlist(name)) != 1 for name in request.query_params
    ):
        raise ValidationError("查询参数不能重复。")
    serializer = BorrowQuerySerializer(data=request.query_params.dict())
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def filtered_records(values):
    records = BorrowRecord.objects.all()
    if not values["include_archived"]:
        records = records.filter(archived_at__isnull=True)
    status = values.get("status")
    if status == "OVERDUE":
        records = records.filter(
            status=BorrowRecord.Status.ACTIVE, due_at__lt=timezone.now()
        )
    elif status:
        records = records.filter(status=status)
    for name in ("user_id", "book_id"):
        if name in values:
            records = records.filter(**{name: values[name]})
    shanghai = ZoneInfo("Asia/Shanghai")
    if "created_from" in values:
        start = datetime.combine(values["created_from"], time.min, shanghai)
        records = records.filter(created_at__gte=start)
    if "created_to" in values:
        end = datetime.combine(
            values["created_to"] + timedelta(days=1), time.min, shanghai
        )
        records = records.filter(created_at__lt=end)
    return records


def page_response(records, values):
    count = records.count()
    page, size = values["page"], values["page_size"]
    start = (page - 1) * size
    if page > 1 and start >= count:
        raise NotFound("页码超出范围。")
    results = records.order_by(values["ordering"], "id")[start : start + size]
    return Response(
        {
            "count": count,
            "page": page,
            "page_size": size,
            "results": BorrowRecordSerializer(results, many=True).data,
        }
    )


class BorrowListView(APIView):
    def get(self, request):
        current_admin(request)
        values = query_values(request)
        return page_response(filtered_records(values), values)

    def post(self, request):
        serializer = BorrowCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_id = subject(request)
        book_id = serializer.validated_data["book_id"]
        request_key = key_header(request)
        user = user_eligibility(user_id, access(request))
        existing = BorrowRecord.objects.filter(request_key=request_key).first()
        if existing:
            if existing.user_id != user_id or existing.book_id != book_id:
                raise Conflict("幂等编号已用于其他借阅请求。")
            if existing.status == BorrowRecord.Status.PENDING:
                existing = advance(existing.pk)
            return record_response(existing)
        book = book_availability(book_id)
        record, created = create_intent(
            user_id, book_id, request_key, user, book, request.request_id
        )
        if record.status == BorrowRecord.Status.PENDING:
            record = advance(record.pk)
        return record_response(record, created=created)


class MyBorrowListView(APIView):
    def get(self, request):
        values = query_values(request)
        if "user_id" in values and values["user_id"] != subject(request):
            raise PermissionDenied("不能查询其他用户的记录。")
        if values["include_archived"]:
            raise PermissionDenied("归档记录仅供管理员审计。")
        return page_response(
            filtered_records(values).filter(user_id=subject(request)), values
        )


class BorrowDetailView(APIView):
    def get(self, request, pk):
        record = record_or_404(pk)
        if record.user_id != subject(request) or record.archived_at is not None:
            current_admin(request)
        return Response(BorrowRecordSerializer(record).data)

    @transaction.atomic
    def patch(self, request, pk):
        current_admin(request)
        try:
            record = BorrowRecord.objects.select_for_update().get(pk=validate_id(pk))
        except BorrowRecord.DoesNotExist:
            raise NotFound("借阅记录不存在。")
        if (
            record.archived_at is not None
            or record.status != BorrowRecord.Status.ACTIVE
        ):
            raise Conflict("只能修改未归档且借阅中的到期日。")
        serializer = DueDateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        due = serializer.validated_data["due_at"]
        if due <= record.borrowed_at:
            raise ValidationError({"due_at": "到期日必须晚于借出时间。"})
        record.due_at = due
        record.save(update_fields=["due_at", "updated_at"])
        return Response(BorrowRecordSerializer(record).data)

    @transaction.atomic
    def delete(self, request, pk):
        current_admin(request)
        try:
            record = BorrowRecord.objects.select_for_update().get(pk=validate_id(pk))
        except BorrowRecord.DoesNotExist:
            raise NotFound("借阅记录不存在。")
        if record.archived_at is not None:
            raise NotFound("记录已归档。")
        if record.status not in (
            BorrowRecord.Status.RETURNED,
            BorrowRecord.Status.FAILED,
        ):
            raise Conflict("只能归档已结束的借阅记录。")
        record.archived_at = timezone.now()
        record.save(update_fields=["archived_at", "updated_at"])
        return Response(status=204)


class BorrowReturnView(APIView):
    def post(self, request, pk):
        if request.data:
            raise ValidationError("归还请求体必须为空。")
        record = record_or_404(pk)
        actor = subject(request)
        if record.user_id != actor:
            current_admin(request)
            admin = True
        else:
            user_eligibility(actor, access(request))
            admin = False
        key = key_header(request)
        record = begin_return(record.pk, key, actor, is_admin=admin)
        if record.status == BorrowRecord.Status.RETURN_PENDING:
            record = advance(record.pk)
        return record_response(record)
