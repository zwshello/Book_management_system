"""Stage 6: verify real four-service statistics over isolated MySQL schemas."""

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
NAMES = ("user-service", "book-service", "borrow-service", "statistics-service")
ENV = {name: dotenv_values(ROOT / "services" / name / ".env") for name in NAMES}
MARKER = "phase6_" + uuid.uuid4().hex[:12]
PASSWORD = secrets.token_urlsafe(24) + "!"


def environment(name):
    source = ENV[name]
    env = os.environ.copy()
    if name != "statistics-service":
        database = source.get("MYSQL_TEST_DATABASE", name.split("-")[0] + "_db_test")
        if database == source["MYSQL_DATABASE"] or not database.endswith("_test"):
            raise RuntimeError("HTTP verification requires an isolated *_test schema")
        env["MYSQL_DATABASE"] = database
    env.update(PHASE6_MARKER=MARKER, PHASE6_PASSWORD=PASSWORD,
               USER_SERVICE_URL="http://127.0.0.1:8001",
               BOOK_SERVICE_URL="http://127.0.0.1:8002",
               BORROW_SERVICE_URL="http://127.0.0.1:8003")
    return env


def manage(name, code):
    guard = "from django.conf import settings; assert settings.DATABASES['default']['NAME']==settings.DATABASES['default']['TEST']['NAME']; "
    result = subprocess.run([sys.executable, "manage.py", "shell", "-v", "0", "-c", guard + code], cwd=ROOT / "services" / name, env=environment(name), capture_output=True, text=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise RuntimeError(f"{name} isolated fixture command failed: {result.stderr[-800:]}")


def call(port, method, path, expected, data=None, access=None, key=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access:
        headers["Authorization"] = "Bearer " + access
    if key:
        headers["Idempotency-Key"] = str(key)
    request = Request(f"http://127.0.0.1:{port}{path}", method=method, headers=headers, data=json.dumps(data).encode() if data is not None else None)
    try:
        response = urlopen(request, timeout=12)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        raw = response.read()
        try:
            body = json.loads(raw) if raw else None
        except ValueError:
            if status != 404:
                raise
            body = None
    if status != expected:
        raise AssertionError(f"{method} {port}{path}: expected {expected}, received {status}, code={body.get('code') if isinstance(body, dict) else None}")
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
    logdir = ROOT / "tmp" / "phase6-http"
    logdir.mkdir(parents=True, exist_ok=True)
    try:
        manage("user-service", "import os; from accounts.models import User; m=os.environ['PHASE6_MARKER']; p=os.environ['PHASE6_PASSWORD']; User.objects.create_user(m+'_admin',m+'_admin@example.com',p,role='ADMIN'); User.objects.create_user(m+'_reader',m+'_reader@example.com',p)")
        for name, port in zip(NAMES, (8001, 8002, 8003, 8004)):
            stream = (logdir / (name + ".log")).open("w", encoding="utf-8")
            streams.append(stream)
            process = subprocess.Popen([sys.executable, "manage.py", "runserver", f"127.0.0.1:{port}", "--noreload"], cwd=ROOT / "services" / name, env=environment(name), stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            processes.append(process)
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError(f"{name} exited; inspect tmp/phase6-http")
                try:
                    call(port, "GET", "/health/live", 200)
                    break
                except URLError:
                    time.sleep(.2)
            else:
                raise RuntimeError(f"{name} startup timeout")
        def login(label):
            return call(8001, "POST", "/api/v1/auth/login", 200, {"username": MARKER + label, "password": PASSWORD})
        admin, reader = login("_admin"), login("_reader")
        user_ids = [admin["user"]["id"], reader["user"]["id"]]
        category = call(8002, "POST", "/api/v1/categories", 201, {"name": MARKER}, admin["access"])
        category_id = category["id"]
        def new_book(copies, available=None):
            payload = {"title": MARKER + " Book", "author": "Integration", "isbn": isbn(), "category": category_id, "total_copies": copies}
            if available is not None:
                payload["available_copies"] = available
            book = call(8002, "POST", "/api/v1/books", 201, payload, admin["access"])
            book_ids.append(book["id"])
            return book["id"]
        first = new_book(2)
        new_book(1, 0)
        call(8003, "POST", "/api/v1/borrows", 201, {"book_id": first}, reader["access"], uuid.uuid4())
        path = "/api/v1/statistics/overview"
        call(8004, "GET", path, 403, access=reader["access"])
        overview = call(8004, "GET", path, 200, access=admin["access"])
        expected = {"user_total": 2, "book_total": 2, "available_book_titles": 1, "available_copies": 1, "borrowed_copies": 1, "current_borrows": 1}
        assert {key: overview[key] for key in expected} == expected, overview
        assert overview["chart"]["values"] == [2, 2, 1, 1, 1]
        for removed in ("categories", "popular-books", "monthly-borrows", "users"):
            call(8004, "GET", "/api/v1/statistics/" + removed, 404, access=admin["access"])
        processes[1].terminate()
        processes[1].wait(timeout=10)
        call(8004, "GET", path, 503, access=admin["access"])
        print("Phase 6 four-service REST/JSON statistics verification passed.")
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        for stream in streams:
            stream.close()
        if book_ids:
            ids = repr(book_ids)
            manage("borrow-service", f"from borrowing.models import BorrowRecord; BorrowRecord.objects.filter(book_id__in={ids}).delete()")
            manage("book-service", f"from catalog.models import Book,StockOperation; StockOperation.objects.filter(book_id__in={ids}).delete(); Book.objects.filter(pk__in={ids}).delete()")
        if user_ids:
            manage("borrow-service", f"from borrowing.models import BorrowerLock; BorrowerLock.objects.filter(user_id__in={user_ids!r}).delete()")
        if category_id:
            manage("book-service", f"from catalog.models import Category; Category.objects.filter(pk={category_id!r}).delete()")
        manage("user-service", "import os; from accounts.models import User; User.objects.filter(username__startswith=os.environ['PHASE6_MARKER']).delete()")
        print("Phase 6 servers stopped and isolated fixtures removed.")


if __name__ == "__main__":
    main()
