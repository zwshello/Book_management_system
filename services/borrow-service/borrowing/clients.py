"""Small bounded REST/JSON clients. Mutating calls are never retried here."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed, NotFound, PermissionDenied

from .errors import Conflict, ServiceUnavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class RemoteError(Exception):
    def __init__(self, status, data):
        self.status = status
        self.data = data


def service_token():
    token = settings.BORROW_SERVICE_TOKEN
    if not token or token.startswith("CHANGE_ME"):
        raise ServiceUnavailable("借阅服务身份凭据未配置。")
    return token


def request_json(base, path, *, access=None, method="GET", payload=None, key=None):
    headers = {
        "Authorization": f"Bearer {service_token()}",
        "Accept": "application/json",
    }
    if access is not None:
        headers["X-User-Access-Token"] = access
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if key is not None:
        headers["Idempotency-Key"] = str(key)
    request = Request(
        base.rstrip("/") + path,
        method=method,
        headers=headers,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
    )
    try:
        response = build_opener(NoRedirect()).open(
            request, timeout=settings.SERVICE_TIMEOUT
        )
    except HTTPError as error:
        response = error
    except (URLError, OSError, TimeoutError) as error:
        raise ServiceUnavailable("依赖服务连接失败或超时。") from error
    try:
        with response:
            raw = response.read(8193)
            status = response.status
    except (URLError, OSError, TimeoutError) as error:
        raise ServiceUnavailable("依赖服务响应中断，结果须按原编号核对。") from error
    if len(raw) > 8192:
        raise ServiceUnavailable("依赖服务响应过大。")
    try:
        data = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ServiceUnavailable("依赖服务未返回合法 JSON。") from error
    if not isinstance(data, dict):
        raise ServiceUnavailable("依赖服务响应结构不合法。")
    if status != 200:
        raise RemoteError(status, data)
    return data


def user_eligibility(subject, access):
    try:
        data = request_json(
            settings.USER_SERVICE_URL,
            f"/internal/v1/users/{subject}/eligibility",
            access=access,
        )
    except RemoteError as error:
        if error.status == 404:
            raise NotFound("用户不存在。") from error
        if error.status == 401 and error.data.get("code") == "UNAUTHENTICATED":
            raise AuthenticationFailed("用户令牌或当前账户无效。") from error
        if error.status == 403:
            raise PermissionDenied("当前用户无权执行此操作。") from error
        raise ServiceUnavailable("用户服务无法确认账户。") from error
    if (
        data.get("id") != str(subject)
        or data.get("role") not in {"USER", "ADMIN"}
        or not isinstance(data.get("username"), str)
        or not data["username"]
        or data.get("is_active") is not True
        or not isinstance(data.get("can_borrow"), bool)
    ):
        raise ServiceUnavailable("用户服务资格响应不合法。")
    if not data["can_borrow"]:
        raise PermissionDenied("账户当前不可借。")
    return data


def book_availability(book_id):
    try:
        data = request_json(
            settings.BOOK_SERVICE_URL, f"/internal/v1/books/{book_id}/availability"
        )
    except RemoteError as error:
        if error.status == 404:
            raise NotFound("图书不存在。") from error
        raise ServiceUnavailable("图书服务暂不可用。") from error
    if (
        data.get("id") != str(book_id)
        or data.get("status") not in {"ACTIVE", "ARCHIVED"}
        or not isinstance(data.get("title"), str)
        or not data["title"]
        or not isinstance(data.get("isbn"), str)
        or not isinstance(data.get("available"), bool)
        or type(data.get("available_copies")) is not int
        or type(data.get("total_copies")) is not int
        or not 0 <= data["available_copies"] <= data["total_copies"]
    ):
        raise ServiceUnavailable("图书服务可借响应不合法。")
    if (
        data["status"] != "ACTIVE"
        or not data["available"]
        or data["available_copies"] == 0
    ):
        raise Conflict("图书当前不可借或库存不足。")
    return data


def validate_operation(data, record, kind, key):
    expected = {
        "operation_key": str(key),
        "borrow_id": str(record.pk),
        "book_id": str(record.book_id),
        "kind": kind,
    }
    if (
        any(data.get(field) != value for field, value in expected.items())
        or type(data.get("success")) is not bool
        or not isinstance(data.get("code"), str)
        or type(data.get("total_copies")) is not int
        or type(data.get("available_copies")) is not int
        or not 0 <= data["available_copies"] <= data["total_copies"]
    ):
        raise ServiceUnavailable("库存操作响应不合法。")
    return data


def operation_result(record, kind):
    key = record.reservation_key if kind == "RESERVE" else record.release_key
    try:
        result = request_json(
            settings.BOOK_SERVICE_URL, f"/internal/v1/books/operations/{key}"
        )
    except RemoteError as error:
        if error.status == 404:
            return None
        raise ServiceUnavailable("无法核对库存操作。") from error
    return validate_operation(result, record, kind, key)


def execute_stock(record, kind):
    key = record.reservation_key if kind == "RESERVE" else record.release_key
    suffix = "reservations" if kind == "RESERVE" else "releases"
    try:
        result = request_json(
            settings.BOOK_SERVICE_URL,
            f"/internal/v1/books/{record.book_id}/{suffix}",
            method="POST",
            payload={"borrow_id": str(record.pk)},
            key=key,
        )
    except RemoteError as error:
        if error.status == 409:
            details = error.data.get("details")
            result = details.get("operation") if isinstance(details, dict) else None
            if isinstance(result, dict):
                return validate_operation(result, record, kind, key)
            raise ServiceUnavailable("库存冲突结果不完整，请按原编号核对。") from error
        if error.status == 404:
            return {
                "success": False,
                "code": "BOOK_NOT_FOUND",
                "operation_key": str(key),
                "borrow_id": str(record.pk),
                "book_id": str(record.book_id),
                "kind": kind,
                "total_copies": 0,
                "available_copies": 0,
            }
        raise ServiceUnavailable("库存操作结果不明，请按原编号核对。") from error
    return validate_operation(result, record, kind, key)
