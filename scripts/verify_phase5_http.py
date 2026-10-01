"""Real three-service REST/JSON verification on isolated MySQL test schemas."""

import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("user-service", "book-service", "borrow-service")
ENV = {name: dotenv_values(ROOT / "services" / name / ".env") for name in NAMES}
MARKER = "phase5_" + uuid.uuid4().hex[:12]
PASSWORD = secrets.token_urlsafe(24) + "!"


def environment(name):
    source = ENV[name]
    database = source.get("MYSQL_TEST_DATABASE", name.split("-")[0] + "_db_test")
    if database == source["MYSQL_DATABASE"] or not database.endswith("_test"):
        raise RuntimeError("HTTP verification requires an isolated *_test schema")
    env = os.environ.copy()
    env.update(
        MYSQL_DATABASE=database,
        PHASE5_MARKER=MARKER,
        PHASE5_PASSWORD=PASSWORD,
        USER_SERVICE_URL="http://127.0.0.1:8001",
        BOOK_SERVICE_URL="http://127.0.0.1:8002",
    )
    return env


def manage(name, code):
    guard = "from django.conf import settings; assert settings.DATABASES['default']['NAME'] == settings.DATABASES['default']['TEST']['NAME']; "
    result = subprocess.run(
        [sys.executable, "manage.py", "shell", "-v", "0", "-c", guard + code],
        cwd=ROOT / "services" / name,
        env=environment(name),
        capture_output=True,
        text=True,
        timeout=30,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError(
            f"{name} isolated fixture command failed: {result.stderr[-800:]}"
        )


def call(port, method, path, expected, data=None, access=None, key=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access:
        headers["Authorization"] = "Bearer " + access
    if key:
        headers["Idempotency-Key"] = str(key)
    request = Request(
        f"http://127.0.0.1:{port}{path}",
        method=method,
        headers=headers,
        data=json.dumps(data).encode() if data is not None else None,
    )
    try:
        response = urlopen(request, timeout=12)
    except HTTPError as error:
        response = error
    with response:
        raw = response.read()
        body = json.loads(raw) if raw else None
        status = response.status
    if status != expected:
        raise AssertionError(
            f"{method} {port}{path}: expected {expected}, got {status}, code={body.get('code') if isinstance(body, dict) else None}"
        )
    print(f"{method} {port}{path}: {status}")
    return body


def isbn():
    prefix = "978" + f"{secrets.randbelow(1000000000):09d}"
    check = (-sum(int(c) * (1 if i % 2 == 0 else 3) for i, c in enumerate(prefix))) % 10
    return prefix + str(check)


def main():
    processes, streams = [], []
    category_id = None
    book_ids = []
    user_ids = []
    logdir = ROOT / "tmp" / "phase5-http"
    logdir.mkdir(parents=True, exist_ok=True)
    try:
        manage(
            "user-service",
            "import os; from accounts.models import User; m=os.environ['PHASE5_MARKER']; p=os.environ['PHASE5_PASSWORD']; User.objects.create_user(m+'_admin',m+'_admin@example.com',p,role='ADMIN'); User.objects.create_user(m+'_reader',m+'_reader@example.com',p); User.objects.create_user(m+'_reader2',m+'_reader2@example.com',p)",
        )
        for name, port in (
            ("user-service", 8001),
            ("book-service", 8002),
            ("borrow-service", 8003),
        ):
            stream = (logdir / (name + ".log")).open("w", encoding="utf-8")
            streams.append(stream)
            process = subprocess.Popen(
                [
                    sys.executable,
                    "manage.py",
                    "runserver",
                    f"127.0.0.1:{port}",
                    "--noreload",
                ],
                cwd=ROOT / "services" / name,
                env=environment(name),
                stdout=stream,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited; inspect tmp/phase5-http")
                try:
                    call(port, "GET", "/health/live", 200)
                    break
                except URLError:
                    time.sleep(0.2)
            else:
                raise RuntimeError(f"{name} startup timeout")

        def login(label):
            return call(
                8001,
                "POST",
                "/api/v1/auth/login",
                200,
                {"username": MARKER + label, "password": PASSWORD},
            )

        admin, reader, reader2 = login("_admin"), login("_reader"), login("_reader2")
        user_ids = [entry["user"]["id"] for entry in (admin, reader, reader2)]
        category = call(
            8002, "POST", "/api/v1/categories", 201, {"name": MARKER}, admin["access"]
        )
        category_id = category["id"]

        def new_book(copies):
            book = call(
                8002,
                "POST",
                "/api/v1/books",
                201,
                {
                    "title": MARKER + " Book",
                    "author": "Integration",
                    "isbn": isbn(),
                    "category": category_id,
                    "total_copies": copies,
                },
                admin["access"],
            )
            book_ids.append(book["id"])
            return book["id"]

        book_id = new_book(2)
        fresh_books = [new_book(1), new_book(1)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_time_results = list(
                pool.map(
                    lambda target: call(
                        8003,
                        "POST",
                        "/api/v1/borrows",
                        201,
                        {"book_id": target},
                        admin["access"],
                        uuid.uuid4(),
                    ),
                    fresh_books,
                )
            )
        assert len(first_time_results) == 2
        print("First-time same-user concurrent intents: two independent 201 results.")
        key = uuid.uuid4()
        record = call(
            8003,
            "POST",
            "/api/v1/borrows",
            201,
            {"book_id": book_id},
            reader["access"],
            key,
        )
        assert (
            record["status"] == "ACTIVE"
            and record["book_title_snapshot"] == MARKER + " Book"
        )
        assert (
            call(
                8003,
                "POST",
                "/api/v1/borrows",
                200,
                {"book_id": book_id},
                reader["access"],
                key,
            )["id"]
            == record["id"]
        )
        stock_path = f"/internal/v1/books/{book_id}/availability"
        service = ENV["book-service"]["BORROW_SERVICE_TOKEN"]
        assert (
            call(8002, "GET", stock_path, 200, access=service)["available_copies"] == 1
        )
        assert (
            call(8003, "GET", "/api/v1/borrows/me", 200, access=reader["access"])[
                "count"
            ]
            == 1
        )
        call(8003, "GET", "/api/v1/borrows", 403, access=reader["access"])
        assert (
            call(8003, "GET", "/api/v1/borrows", 200, access=admin["access"])["count"]
            == 3
        )
        call(8002, "DELETE", f"/api/v1/books/{book_id}", 204, access=admin["access"])
        return_key = uuid.uuid4()
        call(
            8003,
            "POST",
            f"/api/v1/borrows/{record['id']}/return",
            200,
            {},
            reader["access"],
            return_key,
        )
        call(
            8003,
            "POST",
            f"/api/v1/borrows/{record['id']}/return",
            200,
            {},
            reader["access"],
            return_key,
        )
        assert (
            call(8002, "GET", stock_path, 200, access=service)["available_copies"] == 2
        )
        one_copy_id = new_book(1)

        # Supply expected status per call without guessing the winning reader.
        def race(identity):
            headers = {
                "Authorization": "Bearer " + identity["access"],
                "Idempotency-Key": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
            request = Request(
                "http://127.0.0.1:8003/api/v1/borrows",
                method="POST",
                headers=headers,
                data=json.dumps({"book_id": one_copy_id}).encode(),
            )
            try:
                response = urlopen(request, timeout=12)
            except HTTPError as error:
                response = error
            with response:
                return response.status, json.loads(response.read())

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(race, (reader, reader2)))
        assert sorted(status for status, _ in outcomes) == [201, 409], outcomes
        assert (
            call(
                8002,
                "GET",
                f"/internal/v1/books/{one_copy_id}/availability",
                200,
                access=service,
            )["available_copies"]
            == 0
        )
        print("Concurrent last-copy race: one 201, one 409; stock zero.")
        winner = reader if outcomes[0][0] == 201 else reader2
        for _ in range(3):
            extra_id = new_book(1)
            call(
                8003,
                "POST",
                "/api/v1/borrows",
                201,
                {"book_id": extra_id},
                winner["access"],
                uuid.uuid4(),
            )
        candidates = [new_book(1), new_book(1)]

        def limit_race(book):
            headers = {
                "Authorization": "Bearer " + winner["access"],
                "Idempotency-Key": str(uuid.uuid4()),
                "Content-Type": "application/json",
            }
            request = Request(
                "http://127.0.0.1:8003/api/v1/borrows",
                method="POST",
                headers=headers,
                data=json.dumps({"book_id": book}).encode(),
            )
            try:
                response = urlopen(request, timeout=12)
            except HTTPError as error:
                response = error
            with response:
                return response.status

        with ThreadPoolExecutor(max_workers=2) as pool:
            limit_results = list(pool.map(limit_race, candidates))
        assert sorted(limit_results) == [201, 409], limit_results
        print("Concurrent five-book limit: one 201, one 409.")
        print("Phase 5 real REST/JSON verification passed on isolated schemas.")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        for stream in streams:
            stream.close()
        if book_ids:
            ids = repr(book_ids)
            manage(
                "borrow-service",
                f"from borrowing.models import BorrowRecord; BorrowRecord.objects.filter(book_id__in={ids}).delete()",
            )
            manage(
                "book-service",
                f"from catalog.models import Book,StockOperation; StockOperation.objects.filter(book_id__in={ids}).delete(); Book.objects.filter(pk__in={ids}).delete()",
            )
        if user_ids:
            manage(
                "borrow-service",
                f"from borrowing.models import BorrowerLock; BorrowerLock.objects.filter(user_id__in={user_ids!r}).delete()",
            )
        if category_id:
            manage(
                "book-service",
                f"from catalog.models import Category; Category.objects.filter(pk={category_id!r}).delete()",
            )
        manage(
            "user-service",
            "import os; from accounts.models import User; User.objects.filter(username__startswith=os.environ['PHASE5_MARKER']).delete()",
        )
        print("Phase 5 runserver processes stopped and isolated fixtures removed.")


if __name__ == "__main__":
    main()
