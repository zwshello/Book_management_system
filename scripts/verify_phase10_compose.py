"""Exercise the phase-8 business journeys through the Docker gateway.

Creates uniquely named fixtures in the development databases and removes only
those fixtures afterwards. Never run this script against production data.
"""

import json
import os
import re
import secrets
import shutil
import subprocess
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import verify_phase8_http as journeys


ROOT = Path(__file__).resolve().parent.parent
BASE_URL = os.getenv("PHASE10_GATEWAY_URL", "http://127.0.0.1:8080").rstrip("/")
DOCKER = shutil.which("docker")
if not DOCKER and os.name == "nt":
    candidate = Path(os.environ.get("LOCALAPPDATA", "")) / (
        "Programs/DockerDesktop/resources/bin/docker.exe"
    )
    if candidate.is_file():
        DOCKER = str(candidate)


def service_shell(service: str, code: str) -> str:
    if not DOCKER:
        raise RuntimeError("Docker CLI not found; set PATH before verification")
    prefix = (
        "import os; "
        f"os.environ['PHASE8_MARKER']={journeys.MARKER!r}; "
        f"os.environ['PHASE8_PASSWORD']={journeys.PASSWORD!r}; "
    )
    result = subprocess.run(
        [DOCKER, "compose", "exec", "-T", service, "python", "manage.py", "shell", "-v", "0"],
        cwd=ROOT,
        input=prefix + code + "\n",
        text=True,
        capture_output=True,
        timeout=90,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{service} fixture operation failed: {result.stderr[-1000:]}")
    return result.stdout.strip()


def gateway_call(name, method, path, expected, data=None, access=None, key=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access:
        headers["Authorization"] = "Bearer " + access
    if key:
        headers["Idempotency-Key"] = str(key)
    request = Request(
        BASE_URL + path,
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        response = urlopen(request, timeout=20)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        content_type = response.headers.get("Content-Type", "")
        raw = response.read()
    body = json.loads(raw) if raw and "application/json" in content_type else None
    if status != expected:
        code = body.get("code") if isinstance(body, dict) else None
        raise AssertionError(
            f"{method} gateway{path}: expected {expected}, got {status}, code={code}"
        )
    print(f"{method} gateway{path.split('?')[0]}: {status}", flush=True)
    return body


def check_frontend():
    with urlopen(BASE_URL + "/gateway/health", timeout=15) as response:
        assert response.status == 200
    with urlopen(BASE_URL + "/login", timeout=15) as response:
        page = response.read().decode("utf-8")
        assert response.status == 200 and "<html" in page.lower()
    match = re.search(r"/assets/[^\"']+\.js", page)
    assert match, "Frontend entry script missing from built HTML"
    with urlopen(BASE_URL + match.group(), timeout=15) as response:
        assert response.status == 200
    print("Gateway, Vue history fallback and built JavaScript: 200", flush=True)


def main():
    journeys.MARKER = "phase10_" + uuid.uuid4().hex[:12]
    journeys.PASSWORD = secrets.token_urlsafe(24) + "!"
    journeys.call = gateway_call
    journeys.fixture_shell = service_shell
    check_frontend()
    ids = {"users": [], "categories": [], "books": [], "borrows": []}
    try:
        service_shell(
            "user-service",
            "from accounts.models import User; "
            "import os; m=os.environ['PHASE8_MARKER']; "
            "p=os.environ['PHASE8_PASSWORD']; "
            "User.objects.create_user(m+'_admin',m+'_admin@example.com',p,role='ADMIN')",
        )
        journeys.verify_journeys(ids)
        admin = gateway_call(
            "user-service", "POST", "/api/v1/auth/login", 200,
            {"username": journeys.MARKER + "_admin", "password": journeys.PASSWORD},
        )["access"]
        managed_user = gateway_call(
            "user-service", "POST", "/api/v1/users", 201,
            {
                "username": journeys.MARKER + "_managed",
                "email": journeys.MARKER + "_managed@example.com",
                "password": journeys.PASSWORD,
                "role": "USER",
            }, admin,
        )
        ids["users"].append(managed_user["id"])
        gateway_call(
            "user-service", "PATCH", f"/api/v1/users/{managed_user['id']}", 200,
            {"display_name": "Compose Verified"}, admin,
        )
        gateway_call(
            "user-service", "DELETE", f"/api/v1/users/{managed_user['id']}", 204,
            access=admin,
        )
        managed_category = gateway_call(
            "book-service", "POST", "/api/v1/categories", 201,
            {"name": journeys.MARKER + "_category"}, admin,
        )
        ids["categories"].append(managed_category["id"])
        gateway_call(
            "book-service", "PATCH",
            f"/api/v1/categories/{managed_category['id']}", 200,
            {"description": "Compose Verified"}, admin,
        )
        gateway_call(
            "book-service", "DELETE",
            f"/api/v1/categories/{managed_category['id']}", 204,
            access=admin,
        )
    finally:
        journeys.cleanup(ids)
    print("Phase 10 gateway business journeys and fixture cleanup passed.", flush=True)


if __name__ == "__main__":
    main()
