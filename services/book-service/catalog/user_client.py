import json
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

from .errors import ServiceUnavailable


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def current_authorization(subject, access):
    credential = settings.BOOK_SERVICE_TOKEN
    if not credential or credential.startswith("CHANGE_ME"):
        raise ServiceUnavailable("图书服务身份凭据尚未配置。")
    url = (
        settings.USER_SERVICE_URL.rstrip("/")
        + f"/internal/v1/users/{subject}/authorization"
    )
    request = Request(
        url,
        headers={
            "Authorization": f"Bearer {credential}",
            "X-User-Access-Token": access,
            "Accept": "application/json",
        },
    )
    try:
        with build_opener(NoRedirect()).open(
            request, timeout=settings.USER_SERVICE_TIMEOUT
        ) as response:
            raw = response.read(8193)
            if response.status != 200 or len(raw) > 8192:
                raise ServiceUnavailable("用户服务响应不合法。")
            data = json.loads(raw)
    except HTTPError as error:
        if error.code == 401:
            try:
                body = json.loads(error.read(8192))
                code = body.get("code")
                if code != "UNAUTHENTICATED":
                    raise ServiceUnavailable("用户服务身份配置不匹配。")
            except (ValueError, AttributeError):
                raise ServiceUnavailable("用户服务错误响应不合法。")
            raise AuthenticationFailed("用户令牌或当前账户状态无效。")
        raise ServiceUnavailable("无法确认用户当前权限。")
    except (URLError, OSError, ValueError):
        raise ServiceUnavailable("用户服务不可用或响应不合法。")
    if (
        not isinstance(data, dict)
        or not {"id", "role", "is_active", "archived_at"}.issubset(data)
        or data.get("id") != str(subject)
        or data.get("role") not in {"USER", "ADMIN"}
    ):
        raise ServiceUnavailable("用户服务返回的身份信息不合法。")
    if (
        data.get("is_active") is not True
        or data.get("archived_at") is not None
    ):
        raise AuthenticationFailed("账户当前不可用。")
    return data
