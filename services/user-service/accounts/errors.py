from django.db import IntegrityError, OperationalError
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


class Conflict(APIException):
    status_code = 409
    default_detail = "操作与当前用户状态冲突。"
    default_code = "conflict"


def exception_handler(exc, context):
    if isinstance(exc, IntegrityError):
        response = Response({"detail": "用户名或邮箱已存在。"}, status=409)
    elif isinstance(exc, OperationalError):
        response = Response({"detail": "数据库暂不可用。"}, status=503)
    else:
        response = drf_exception_handler(exc, context)
    if response is None:
        return None
    codes = {
        400: ("VALIDATION_ERROR", "输入不合法，请检查 details。"),
        401: ("UNAUTHENTICATED", "认证失败或令牌无效。"),
        403: ("PERMISSION_DENIED", "无权执行此操作。"),
        404: ("NOT_FOUND", "资源不存在。"),
        405: ("METHOD_NOT_ALLOWED", "请求方法不支持。"),
        409: ("CONFLICT", "操作与当前数据冲突。"),
        415: ("UNSUPPORTED_MEDIA_TYPE", "请求必须使用 JSON。"),
        503: ("SERVICE_UNAVAILABLE", "服务暂不可用。"),
    }
    code, message = codes.get(
        response.status_code, ("API_ERROR", "请求失败。")
    )
    request = context.get("request")
    response.data = {
        "code": getattr(exc, "api_code", code),
        "message": message,
        "details": response.data,
        "request_id": getattr(request, "request_id", ""),
    }
    return response
