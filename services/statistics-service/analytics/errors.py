from rest_framework.exceptions import APIException


class ServiceUnavailable(APIException):
    status_code = 503
    default_detail = "上游统计数据暂不可用。"


def exception_handler(exc, context):
    from rest_framework.views import exception_handler as drf_handler

    response = drf_handler(exc, context)
    if response is None:
        return None
    codes = {400: "VALIDATION_ERROR", 401: "UNAUTHENTICATED", 403: "PERMISSION_DENIED", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 415: "UNSUPPORTED_MEDIA_TYPE", 503: "SERVICE_UNAVAILABLE"}
    response.data = {"code": getattr(exc, "api_code", codes.get(response.status_code, "API_ERROR")), "message": "请求未完成，请查看 details。", "details": response.data, "request_id": getattr(context.get("request"), "request_id", "")}
    return response
