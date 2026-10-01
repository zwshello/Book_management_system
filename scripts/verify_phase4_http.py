"""Real user/book HTTP verification, exclusively on isolated MySQL test schemas."""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
SERVICE_ENVS = {
    name: dotenv_values(ROOT / "services" / name / ".env")
    for name in ("user-service", "book-service")
}
MARKER = "phase4_" + uuid.uuid4().hex[:12]
PASSWORD = secrets.token_urlsafe(24) + "!"


def environment(service):
    env = os.environ.copy()
    database = SERVICE_ENVS[service].get("MYSQL_TEST_DATABASE")
    if not database:
        database = (
            "user_db_test" if service == "user-service" else "book_db_test"
        )
    if database == SERVICE_ENVS[service]["MYSQL_DATABASE"]:
        raise RuntimeError(
            "Test database must differ from development database"
        )
    env.update(
        MYSQL_DATABASE=database,
        PHASE4_PASSWORD=PASSWORD,
        PHASE4_MARKER=MARKER,
        USER_SERVICE_URL="http://127.0.0.1:8001",
    )
    return env


def manage(service, code):
    guard = "from django.conf import settings; assert settings.DATABASES['default']['NAME'] == settings.DATABASES['default']['TEST']['NAME']; "
    result = subprocess.run(
        [sys.executable, "manage.py", "shell", "-v", "0", "-c", guard + code],
        cwd=ROOT / "services" / service,
        env=environment(service),
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError(result.stderr)


def call(port, method, path, expected, data=None, access=None, extra=None):
    headers = {"Content-Type": "application/json"}
    if access:
        headers["Authorization"] = "Bearer " + access
    headers.update(extra or {})
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        data=json.dumps(data).encode() if data is not None else None,
        headers=headers,
    )
    try:
        response = urlopen(request, timeout=6)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        raw = response.read()
        body = json.loads(raw) if raw else None
    if status != expected:
        raise AssertionError(
            f"{method} {path}: expected {expected}, received {status}; code={body.get('code') if body else None}"
        )
    print(f"{method} {path}: {status}")
    return body


def main():
    processes, streams = [], []
    category_id = book_id = None
    logdir = ROOT / "tmp" / "phase4-http"
    logdir.mkdir(parents=True, exist_ok=True)
    try:
        manage(
            "user-service",
            "import os; from accounts.models import User; m=os.environ['PHASE4_MARKER']; p=os.environ['PHASE4_PASSWORD']; User.objects.create_user(m+'_admin',m+'_admin@example.com',p,role='ADMIN'); User.objects.create_user(m+'_reader',m+'_reader@example.com',p)",
        )
        for service, port in (("user-service", 8001), ("book-service", 8002)):
            stream = (logdir / (service + ".log")).open("w", encoding="utf-8")
            streams.append(stream)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "manage.py",
                    "runserver",
                    f"127.0.0.1:{port}",
                    "--noreload",
                ],
                cwd=ROOT / "services" / service,
                env=environment(service),
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=(
                    subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                ),
            )
            processes.append(process)
            for attempt in range(100):
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{service} exited; inspect tmp/phase4-http logs"
                    )
                try:
                    call(port, "GET", "/health/live", 200)
                    break
                except URLError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("runserver startup timeout")
        admin = call(
            8001,
            "POST",
            "/api/v1/auth/login",
            200,
            {"username": MARKER + "_admin", "password": PASSWORD},
        )
        reader = call(
            8001,
            "POST",
            "/api/v1/auth/login",
            200,
            {"username": MARKER + "_reader", "password": PASSWORD},
        )
        category = call(
            8002,
            "POST",
            "/api/v1/categories",
            201,
            {"name": MARKER},
            admin["access"],
        )
        category_id = category["id"]
        prefix = "978" + f"{secrets.randbelow(1000000000):09d}"
        isbn = prefix + str(
            (
                -sum(
                    int(c) * (1 if i % 2 == 0 else 3)
                    for i, c in enumerate(prefix)
                )
            )
            % 10
        )
        book = call(
            8002,
            "POST",
            "/api/v1/books",
            201,
            {
                "title": MARKER + " Python",
                "author": "HTTP Test",
                "isbn": isbn,
                "category": category_id,
                "total_copies": 2,
            },
            admin["access"],
        )
        book_id = book["id"]
        path = "/api/v1/books/" + book_id
        call(8002, "GET", path, 200, access=reader["access"])
        call(8002, "POST", "/api/v1/books", 403, {}, reader["access"])
        query = call(
            8002,
            "GET",
            f"/api/v1/books?title=Python&category_id={category_id}&availability=available",
            200,
            access=reader["access"],
        )
        assert query["count"] == 1
        call(
            8002,
            "POST",
            path + "/stock-adjustments",
            200,
            {"total_copies": 3},
            admin["access"],
        )
        credential = SERVICE_ENVS["book-service"]["BORROW_SERVICE_TOKEN"]
        borrow, key = str(uuid.uuid4()), str(uuid.uuid4())
        internal = "/internal/v1/books/" + book_id
        extra = {"Idempotency-Key": key}
        first = call(
            8002,
            "POST",
            internal + "/reservations",
            200,
            {"borrow_id": borrow},
            credential,
            extra,
        )
        assert first == call(
            8002,
            "POST",
            internal + "/reservations",
            200,
            {"borrow_id": borrow},
            credential,
            extra,
        )
        call(
            8002,
            "POST",
            internal + "/reservations",
            401,
            {"borrow_id": borrow},
            reader["access"],
            extra,
        )
        call(8002, "DELETE", path, 204, access=admin["access"])
        call(8002, "GET", path, 404, access=reader["access"])
        released = call(
            8002,
            "POST",
            internal + "/releases",
            200,
            {"borrow_id": borrow},
            credential,
            {"Idempotency-Key": str(uuid.uuid4())},
        )
        assert released["available_copies"] == 3
        call(8002, "PATCH", path, 200, {"status": "ACTIVE"}, admin["access"])
        second = call(
            8001,
            "POST",
            "/api/v1/users",
            201,
            {
                "username": MARKER + "_second",
                "email": MARKER + "_second@example.com",
                "password": PASSWORD,
                "role": "ADMIN",
            },
            admin["access"],
        )
        second_login = call(
            8001,
            "POST",
            "/api/v1/auth/login",
            200,
            {"username": second["username"], "password": PASSWORD},
        )
        call(
            8001,
            "PATCH",
            "/api/v1/users/" + admin["user"]["id"],
            200,
            {"role": "USER"},
            second_login["access"],
        )
        call(
            8002,
            "PATCH",
            path,
            403,
            {"title": "Must Not Change"},
            admin["access"],
        )
        call(
            8001,
            "PATCH",
            "/api/v1/users/" + admin["user"]["id"],
            200,
            {"is_active": False},
            second_login["access"],
        )
        call(
            8002,
            "PATCH",
            path,
            401,
            {"title": "Must Not Change"},
            admin["access"],
        )
        processes[0].terminate()
        processes[0].wait(timeout=10)
        call(
            8002,
            "PATCH",
            path,
            503,
            {"title": "Must Not Change"},
            second_login["access"],
        )
        assert (
            call(8002, "GET", path, 200, access=reader["access"])["title"]
            == MARKER + " Python"
        )
        print(
            "Phase 4 real REST/JSON verification passed on isolated test databases."
        )
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        for stream in streams:
            stream.close()
        if book_id:
            manage(
                "book-service",
                f"from catalog.models import Book,StockOperation; StockOperation.objects.filter(book_id={book_id!r}).delete(); Book.objects.filter(pk={book_id!r}).delete()",
            )
        if category_id:
            manage(
                "book-service",
                f"from catalog.models import Category; Category.objects.filter(pk={category_id!r}).delete()",
            )
        manage(
            "user-service",
            "import os; from accounts.models import User; m=os.environ['PHASE4_MARKER']; User.objects.filter(username__in=[m+'_admin',m+'_reader',m+'_second']).delete()",
        )
        print(
            "Validation servers stopped and this run's test fixtures removed."
        )


if __name__ == "__main__":
    main()
