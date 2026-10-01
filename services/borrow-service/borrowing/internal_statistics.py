"""Borrowed and current counts computed only from borrow_db."""

from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import StatisticsServiceAuthentication
from .models import BorrowRecord


class BorrowSummaryView(APIView):
    authentication_classes = [StatisticsServiceAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.query_params:
            raise ValidationError("此接口不接受查询参数。")
        return Response(
            {
                "borrowed_copies": BorrowRecord.objects.filter(
                    status__in=[
                        BorrowRecord.Status.ACTIVE,
                        BorrowRecord.Status.RETURN_PENDING,
                    ]
                ).count(),
                "current_borrows": BorrowRecord.objects.filter(
                    status=BorrowRecord.Status.ACTIVE
                ).count(),
            }
        )
