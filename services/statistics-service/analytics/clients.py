"""Bounded read-only REST clients; no business database access."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

from .errors import ServiceUnavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


class RemoteError(Exception):
    def __init__(self, status, body):
        self.status = status
        self.body = body


def credential():
    value = settings.STATISTICS_SERVICE_TOKEN
    if not value or value.startswith("CHANGE_ME"):
        raise ServiceUnavailable("统计服务身份凭据未配置。")
    return value


def get_json(base, path, *, access=None):
    headers = {
        "Authorization": f"Bearer {credential()}",
        "Accept": "application/json",
    }
    if access is not None:
        headers["X-User-Access-Token"] = access
    request = Request(base.rstrip("/") + path, headers=headers)
    try:
        response = build_opener(NoRedirect()).open(
            request, timeout=settings.SERVICE_TIMEOUT
        )
    except HTTPError as error:
        response = error
    except (URLError, OSError, TimeoutError) as error:
        raise ServiceUnavailable("上游服务连接失败或超时。") from error
    try:
        with response:
            raw = response.read(8193)
            status = response.status
    except (URLError, OSError, TimeoutError) as error:
        raise ServiceUnavailable("上游服务响应中断。") from error
    if len(raw) > 8192:
        raise ServiceUnavailable("上游服务响应过大。")
    try:
        body = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise ServiceUnavailable("上游服务响应不是合法 JSON。") from error
    if not isinstance(body, dict):
        raise ServiceUnavailable("上游服务响应结构不合法。")
    if status != 200:
        raise RemoteError(status, body)
    return body


def user_authorization(subject, access):
    try:
        body = get_json(
            settings.USER_SERVICE_URL,
            f"/internal/v1/users/{subject}/authorization",
            access=access,
        )
    except RemoteError as error:
        if error.status == 401 and error.body.get("code") == "UNAUTHENTICATED":
            raise AuthenticationFailed("用户令牌或账户当前无效。") from error
        raise ServiceUnavailable("用户服务无法确认当前角色。") from error
    if (
        body.get("id") != str(subject)
        or body.get("role") not in {"USER", "ADMIN"}
        or body.get("is_active") is not True
        or body.get("archived_at") is not None
    ):
        raise ServiceUnavailable("用户服务授权响应不合法。")
    return body


def summary(base, path, fields):
    try:
        body = get_json(base, path)
    except RemoteError as error:
        raise ServiceUnavailable("业务服务汇总暂不可用。") from error
    if any(type(body.get(key)) is not int or body[key] < 0 for key in fields):
        raise ServiceUnavailable("业务服务汇总响应不合法。")
    return body


def user_summary():
    return summary(
        settings.USER_SERVICE_URL,
        "/internal/v1/users/summary",
        ("total_users",),
    )


def book_summary():
    body = summary(
        settings.BOOK_SERVICE_URL,
        "/internal/v1/books/summary",
        ("book_total", "available_titles", "available_copies"),
    )
    if body["available_titles"] > body["book_total"]:
        raise ServiceUnavailable("图书汇总响应不合法。")
    return body


def borrow_summary():
    body = summary(
        settings.BORROW_SERVICE_URL,
        "/internal/v1/borrows/summary",
        ("borrowed_copies", "current_borrows"),
    )
    if body["borrowed_copies"] < body["current_borrows"]:
        raise ServiceUnavailable("借阅汇总响应不合法。")
    return body
