from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from .clients import book_summary, borrow_summary, user_authorization, user_summary


class OverviewView(APIView):
    def get(self, request):
        if request.auth.get("role") != "ADMIN":
            raise PermissionDenied("完整统计仅对管理员开放。")
        access = request.headers["Authorization"].split()[1]
        account = user_authorization(request.user.id, access)
        if account["role"] != "ADMIN":
            raise PermissionDenied("当前账户不是管理员。")
        if request.query_params:
            raise ValidationError("此接口不接受查询参数。")
        users = user_summary()
        books = book_summary()
        borrows = borrow_summary()
        values = [
            users["total_users"],
            books["book_total"],
            books["available_copies"],
            borrows["borrowed_copies"],
            borrows["current_borrows"],
        ]
        return Response(
            {
                "user_total": values[0],
                "book_total": values[1],
                "available_book_titles": books["available_titles"],
                "available_copies": values[2],
                "borrowed_copies": values[3],
                "current_borrows": values[4],
                "chart": {
                    "labels": [
                        "用户总数",
                        "图书书目数",
                        "可借册数",
                        "已借册数",
                        "当前借阅数",
                    ],
                    "values": values,
                },
            }
        )
