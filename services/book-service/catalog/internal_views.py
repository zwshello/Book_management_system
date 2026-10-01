from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.serializers import UUIDField
from rest_framework.views import APIView

from .authentication import BorrowServiceAuthentication
from .errors import Conflict
from .models import Book, StockOperation
from .serializers import StockRequestSerializer
from .stock import operate


class InternalBase(APIView):
    authentication_classes = [BorrowServiceAuthentication]
    permission_classes = [IsAuthenticated]


class AvailabilityView(InternalBase):
    def get(self, request, pk):
        pk = UUIDField().run_validation(pk)
        try:
            book = Book.objects.get(pk=pk)
        except Book.DoesNotExist:
            raise NotFound("图书不存在。")
        return Response(
            {
                "id": str(book.pk),
                "title": book.title,
                "isbn": book.isbn,
                "status": book.status,
                "total_copies": book.total_copies,
                "available_copies": book.available_copies,
                "available": book.status == Book.Status.ACTIVE
                and book.available_copies > 0,
            }
        )


class StockOperationView(InternalBase):
    kind = None

    def post(self, request, pk):
        pk = UUIDField().run_validation(pk)
        key = UUIDField().run_validation(request.headers.get("Idempotency-Key"))
        serializer = StockRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        operation = operate(pk, serializer.validated_data["borrow_id"], key, self.kind)
        if not operation.result["success"]:
            # Raise after the stock transaction commits, preserving failure
            # results so a retry does not unexpectedly become a reservation.
            error = Conflict("库存操作未成功。")
            # DRF's APIException constructor stringifies nested scalars. Keep
            # the persisted operation JSON typed for the borrow coordinator.
            error.detail = {"operation": operation.result}
            error.api_code = operation.result["code"]
            raise error
        return Response(operation.result)


class ReservationView(StockOperationView):
    kind = StockOperation.Kind.RESERVE


class ReleaseView(StockOperationView):
    kind = StockOperation.Kind.RELEASE


class OperationDetailView(InternalBase):
    def get(self, request, operation_key):
        key = UUIDField().run_validation(operation_key)
        try:
            operation = StockOperation.objects.get(operation_key=key)
        except StockOperation.DoesNotExist:
            raise NotFound("操作尚未执行。")
        return Response(operation.result)
