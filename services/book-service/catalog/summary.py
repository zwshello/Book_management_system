from django.db.models import Count, Q, Sum
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .authentication import StatisticsServiceAuthentication
from .models import Book


class BookSummaryView(APIView):
    authentication_classes = [StatisticsServiceAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.query_params:
            raise ValidationError("此接口不接受查询参数。")
        active = Book.objects.filter(status=Book.Status.ACTIVE)
        totals = active.aggregate(
            book_total=Count("id"),
            available_sum=Sum("available_copies"),
            available_titles=Count("id", filter=Q(available_copies__gt=0)),
        )
        return Response(
            {
                "book_total": totals["book_total"],
                "available_copies": totals["available_sum"] or 0,
                "available_titles": totals["available_titles"],
            }
        )
