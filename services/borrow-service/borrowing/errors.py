from django.db import IntegrityError, OperationalError
from rest_framework.exceptions import APIException
from rest_framework.response import Response


class Conflict(APIException):
    status_code = 409
    default_detail = "操作与当前状态冲突。"


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "依赖服务暂不可用。"


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler

    if isinstance(exc, IntegrityError):
        response = Response({"detail": "唯一性或数据约束冲突。"}, status=409)
    elif isinstance(exc, OperationalError):
        response = Response(
            {"detail": "数据库暂不可用；已有待处理请求须按原编号核对。"}, status=503
        )
    else:
        response = drf_handler(exc, context)
    if response is None:
        return None
    codes = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHENTICATED",
        403: "PERMISSION_DENIED",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        415: "UNSUPPORTED_MEDIA_TYPE",
        503: "SERVICE_UNAVAILABLE",
    }
    response.data = {
        "code": getattr(exc, "api_code", codes.get(response.status_code, "API_ERROR")),
        "message": "请求未完成，请查看 details。",
        "details": response.data,
        "request_id": getattr(context.get("request"), "request_id", ""),
    }
    return response
