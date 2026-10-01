"""Run stage 8 REST/JSON journeys against four isolated MySQL services.

The optional --hold mode keeps the servers and fixtures available for browser
checks. Create tmp/phase8-http/stop to end that mode and remove all fixtures.
"""

import argparse
import json
import os
import secrets
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parent.parent
NAMES = ("user-service", "book-service", "borrow-service", "statistics-service")
PORTS = dict(zip(NAMES, (8101, 8102, 8103, 8104)))
ENV = {name: dotenv_values(ROOT / "services" / name / ".env") for name in NAMES}
ARTIFACTS = ROOT / "tmp" / "phase8-http"
MARKER = "phase8_" + uuid.uuid4().hex[:12]
PASSWORD = os.environ.get("PHASE8_TEST_PASSWORD") or secrets.token_urlsafe(24) + "!"


def environment(name):
    source = ENV[name]
    env = os.environ.copy()
    if name != "statistics-service":
        database = source.get("MYSQL_TEST_DATABASE") or name.split("-")[0] + "_db_test"
        if database == source["MYSQL_DATABASE"] or not database.endswith("_test"):
            raise RuntimeError(
                "Stage 8 HTTP verification requires an isolated *_test schema"
            )
        env["MYSQL_DATABASE"] = database
    env.update(
        PHASE8_MARKER=MARKER,
        PHASE8_PASSWORD=PASSWORD,
        USER_SERVICE_URL="http://127.0.0.1:8101",
        BOOK_SERVICE_URL="http://127.0.0.1:8102",
        BORROW_SERVICE_URL="http://127.0.0.1:8103",
    )
    return env


def manage(name, *args, timeout=60):
    result = subprocess.run(
        [sys.executable, "manage.py", *args],
        cwd=ROOT / "services" / name,
        env=environment(name),
        capture_output=True,
        text=True,
        timeout=timeout,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    if result.returncode:
        raise RuntimeError(
            f"{name} {' '.join(args[:2])} failed: {result.stderr[-1000:]}"
        )
    return result.stdout


def fixture_shell(name, code):
    guard = (
        "from django.conf import settings; "
        "assert settings.DATABASES['default']['NAME'] == "
        "settings.DATABASES['default']['TEST']['NAME']; "
    )
    return manage(name, "shell", "-v", "0", "-c", guard + code)


def call(name, method, path, expected, data=None, access=None, key=None):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    if access:
        headers["Authorization"] = "Bearer " + access
    if key:
        headers["Idempotency-Key"] = str(key)
    request = Request(
        f"http://127.0.0.1:{PORTS[name]}{path}",
        method=method,
        headers=headers,
        data=json.dumps(data).encode("utf-8") if data is not None else None,
    )
    try:
        response = urlopen(request, timeout=15)
    except HTTPError as error:
        response = error
    with response:
        status = response.status
        raw = response.read()
        content_type = response.headers.get("Content-Type", "")
        body = json.loads(raw) if raw and "application/json" in content_type else None
    if status != expected:
        code = body.get("code") if isinstance(body, dict) else None
        raise AssertionError(
            f"{method} {name}{path}: expected {expected}, received {status}, code={code}"
        )
    print(f"{method} {name}{path.split('?')[0]}: {status}", flush=True)
    return body


def isbn():
    prefix = "978" + f"{secrets.randbelow(1000000000):09d}"
    checksum = (
        -sum(
            int(digit) * (1 if index % 2 == 0 else 3)
            for index, digit in enumerate(prefix)
        )
    ) % 10
    return prefix + str(checksum)


def query(path, **values):
    return path + "?" + urlencode(values)


def start_servers(processes, streams):
    for name in NAMES:
        port = PORTS[name]
        stream = (ARTIFACTS / f"{name}.log").open("w", encoding="utf-8")
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
                raise RuntimeError(
                    f"{name} exited; inspect {ARTIFACTS / (name + '.log')}"
                )
            try:
                call(name, "GET", "/health/live", 200)
                break
            except URLError:
                time.sleep(0.2)
        else:
            raise RuntimeError(f"{name} startup timeout")


def verify_journeys(ids):
    user = "user-service"
    book = "book-service"
    borrow = "borrow-service"
    stats = "statistics-service"
    login = lambda label: call(
        user,
        "POST",
        "/api/v1/auth/login",
        200,
        {"username": MARKER + label, "password": PASSWORD},
    )
    admin = login("_admin")
    admin_access = admin["access"]
    ids["users"].append(admin["user"]["id"])

    # A: administrator creates and edits catalogue data.
    category = call(
        book,
        "POST",
        "/api/v1/categories",
        201,
        {"name": MARKER, "description": "Stage 8"},
        admin_access,
    )
    ids["categories"].append(category["id"])
    assert (
        call(
            book,
            "GET",
            query("/api/v1/categories", name=MARKER),
            200,
            access=admin_access,
        )["count"]
        == 1
    )
    book_payload = {
        "title": MARKER + " Python Guide",
        "author": "Stage 8 Author",
        "isbn": isbn(),
        "category": category["id"],
        "total_copies": 2,
        "available_copies": 2,
        "status": "ACTIVE",
    }
    created = call(book, "POST", "/api/v1/books", 201, book_payload, admin_access)
    ids["books"].append(created["id"])
    second = call(
        book,
        "POST",
        "/api/v1/books",
        201,
        {**book_payload, "title": MARKER + " TypeScript Guide", "isbn": isbn()},
        admin_access,
    )
    ids["books"].append(second["id"])
    first_page = call(
        book,
        "GET",
        query(
            "/api/v1/books",
            category_id=category["id"],
            page=1,
            page_size=1,
            ordering="title",
        ),
        200,
        access=admin_access,
    )
    second_page = call(
        book,
        "GET",
        query(
            "/api/v1/books",
            category_id=category["id"],
            page=2,
            page_size=1,
            ordering="title",
        ),
        200,
        access=admin_access,
    )
    assert first_page["count"] == second_page["count"] == 2
    assert [first_page["results"][0]["id"], second_page["results"][0]["id"]] == [
        created["id"],
        second["id"],
    ]
    assert call(book, "GET", "/api/v1/books", 200, access=admin_access)["count"] >= 1
    assert (
        call(
            book,
            "GET",
            query("/api/v1/books", title="Python"),
            200,
            access=admin_access,
        )["count"]
        >= 1
    )
    assert (
        call(
            book,
            "GET",
            query("/api/v1/books", author="Stage 8"),
            200,
            access=admin_access,
        )["count"]
        >= 1
    )
    assert (
        call(
            book,
            "GET",
            query("/api/v1/books", isbn=created["isbn"]),
            200,
            access=admin_access,
        )["count"]
        == 1
    )
    assert (
        call(
            book,
            "GET",
            query("/api/v1/books", title_exact=created["title"]),
            200,
            access=admin_access,
        )["count"]
        == 1
    )
    combined = call(
        book,
        "GET",
        query(
            "/api/v1/books",
            title="Python",
            category_id=category["id"],
            status="ACTIVE",
            availability="available",
            page=1,
            page_size=1,
            ordering="title",
        ),
        200,
        access=admin_access,
    )
    assert combined["count"] == 1 and combined["results"][0]["id"] == created["id"]
    edited = call(
        book,
        "PATCH",
        f"/api/v1/books/{created['id']}",
        200,
        {"publisher": "Stage 8 Press"},
        admin_access,
    )
    assert edited["publisher"] == "Stage 8 Press"

    # B: administrator creates a reader; reader searches, borrows, and returns.
    reader_payload = {
        "username": MARKER + "_reader",
        "email": MARKER + "_reader@example.com",
        "password": PASSWORD,
        "role": "USER",
    }
    reader = call(user, "POST", "/api/v1/users", 201, reader_payload, admin_access)
    ids["users"].append(reader["id"])
    second_reader = call(
        user,
        "POST",
        "/api/v1/users",
        201,
        {
            **reader_payload,
            "username": MARKER + "_reader2",
            "email": MARKER + "_reader2@example.com",
        },
        admin_access,
    )
    ids["users"].append(second_reader["id"])
    reader_access = login("_reader")["access"]
    assert (
        call(
            book,
            "GET",
            query("/api/v1/books", title="Python", author="Stage", page=1, page_size=1),
            200,
            access=reader_access,
        )["count"]
        == 1
    )
    assert (
        call(book, "GET", f"/api/v1/books/{created['id']}", 200, access=reader_access)[
            "isbn"
        ]
        == created["isbn"]
    )
    borrowed = call(
        borrow,
        "POST",
        "/api/v1/borrows",
        201,
        {"book_id": created["id"]},
        reader_access,
        uuid.uuid4(),
    )
    ids["borrows"].append(borrowed["id"])
    assert borrowed["status"] == "ACTIVE"
    assert (
        call(borrow, "GET", "/api/v1/borrows/me", 200, access=reader_access)["count"]
        >= 1
    )
    after_borrow = call(
        book, "GET", f"/api/v1/books/{created['id']}", 200, access=reader_access
    )
    assert after_borrow["available_copies"] == 1

    # C: administrator sees users, borrowing records, and live statistics.
    users = call(
        user,
        "GET",
        query(
            "/api/v1/users",
            username_contains=MARKER,
            role="USER",
            is_active="true",
            page=1,
            page_size=1,
            ordering="username",
        ),
        200,
        access=admin_access,
    )
    next_users = call(
        user,
        "GET",
        query(
            "/api/v1/users",
            username_contains=MARKER,
            role="USER",
            is_active="true",
            page=2,
            page_size=1,
            ordering="username",
        ),
        200,
        access=admin_access,
    )
    assert users["count"] == next_users["count"] == 2
    assert (
        call(
            user,
            "GET",
            query("/api/v1/users", username=reader["username"]),
            200,
            access=admin_access,
        )["count"]
        == 1
    )
    assert [users["results"][0]["id"], next_users["results"][0]["id"]] == [
        reader["id"],
        second_reader["id"],
    ]
    records = call(
        borrow,
        "GET",
        query(
            "/api/v1/borrows",
            user_id=reader["id"],
            book_id=created["id"],
            status="ACTIVE",
            page=1,
            page_size=1,
            ordering="created_at",
        ),
        200,
        access=admin_access,
    )
    assert records["count"] == 1 and records["results"][0]["id"] == borrowed["id"]
    second_reader_access = login("_reader2")["access"]
    call(
        borrow,
        "GET",
        f"/api/v1/borrows/{borrowed['id']}",
        403,
        access=second_reader_access,
    )
    overview = call(
        stats, "GET", "/api/v1/statistics/overview", 200, access=admin_access
    )
    assert overview["user_total"] >= 2 and overview["book_total"] >= 1
    assert overview["available_copies"] >= 1 and overview["borrowed_copies"] >= 1
    assert overview["current_borrows"] >= 1
    assert len(overview["chart"]["labels"]) == len(overview["chart"]["values"]) == 5
    assert overview["chart"]["values"] == [
        overview[k]
        for k in (
            "user_total",
            "book_total",
            "available_copies",
            "borrowed_copies",
            "current_borrows",
        )
    ]

    # Backend authorization must reject reader writes and administrator statistics.
    call(user, "GET", "/api/v1/users", 403, access=reader_access)
    call(user, "POST", "/api/v1/users", 403, reader_payload, reader_access)
    call(book, "POST", "/api/v1/books", 403, book_payload, reader_access)
    call(
        book,
        "PATCH",
        f"/api/v1/books/{created['id']}",
        403,
        {"title": "Forbidden"},
        reader_access,
    )
    call(book, "DELETE", f"/api/v1/books/{created['id']}", 403, access=reader_access)
    call(stats, "GET", "/api/v1/statistics/overview", 403, access=reader_access)
    call(user, "GET", "/api/v1/users", 401)

    # Invalid forms fail at the API boundary as well as in Element Plus.
    call(
        user,
        "POST",
        "/api/v1/users",
        400,
        {**reader_payload, "username": "x", "email": "x2@example.com"},
        admin_access,
    )
    call(
        user,
        "POST",
        "/api/v1/users",
        400,
        {**reader_payload, "username": MARKER + "_badmail", "email": "invalid"},
        admin_access,
    )
    call(
        book,
        "POST",
        "/api/v1/books",
        400,
        {**book_payload, "isbn": created["isbn"]},
        admin_access,
    )
    call(
        book,
        "POST",
        "/api/v1/books",
        400,
        {**book_payload, "isbn": isbn(), "total_copies": -1},
        admin_access,
    )
    call(
        book,
        "POST",
        "/api/v1/books",
        400,
        {**book_payload, "isbn": isbn(), "title": ""},
        admin_access,
    )
    call(
        book,
        "POST",
        "/api/v1/books",
        400,
        {**book_payload, "isbn": isbn(), "available_copies": 3},
        admin_access,
    )
    call(
        book,
        "GET",
        query("/api/v1/books", ordering="invalid"),
        400,
        access=admin_access,
    )

    returned = call(
        borrow,
        "POST",
        f"/api/v1/borrows/{borrowed['id']}/return",
        200,
        {},
        reader_access,
        uuid.uuid4(),
    )
    assert returned["status"] == "RETURNED"
    assert (
        call(book, "GET", f"/api/v1/books/{created['id']}", 200, access=reader_access)[
            "available_copies"
        ]
        == 2
    )
    assert (
        call(
            borrow,
            "GET",
            query("/api/v1/borrows/me", status="RETURNED", page=1, page_size=1),
            200,
            access=reader_access,
        )["count"]
        == 1
    )
    overview_after = call(
        stats, "GET", "/api/v1/statistics/overview", 200, access=admin_access
    )
    assert overview_after["current_borrows"] == overview["current_borrows"] - 1
    assert overview_after["borrowed_copies"] == overview["borrowed_copies"] - 1
    assert overview_after["available_copies"] == overview["available_copies"] + 1

    # HTTP delete semantics on disposable data; UI confirmation is checked by browser tests.
    disposable_category = call(
        book,
        "POST",
        "/api/v1/categories",
        201,
        {"name": MARKER + "_disposable"},
        admin_access,
    )
    ids["categories"].append(disposable_category["id"])
    disposable_book = call(
        book,
        "POST",
        "/api/v1/books",
        201,
        {
            **book_payload,
            "title": MARKER + " Disposable",
            "isbn": isbn(),
            "category": disposable_category["id"],
        },
        admin_access,
    )
    ids["books"].append(disposable_book["id"])
    call(
        book,
        "DELETE",
        f"/api/v1/books/{disposable_book['id']}",
        204,
        access=admin_access,
    )
    call(
        book,
        "DELETE",
        f"/api/v1/categories/{disposable_category['id']}",
        409,
        access=admin_access,
    )
    print(
        "Stage 8 HTTP journeys A/B/C, queries, validation, authorization and delete passed.",
        flush=True,
    )
    return {
        "base_urls": {name: f"http://127.0.0.1:{port}" for name, port in PORTS.items()},
        "admin": {"username": MARKER + "_admin", "password": PASSWORD},
        "reader": {"username": MARKER + "_reader", "password": PASSWORD},
        "category_id": category["id"],
        "book_id": created["id"],
        "borrow_id": borrowed["id"],
        "marker": MARKER,
    }


def cleanup(ids):
    # Browser tests can create additional marker-prefixed fixtures. Resolve
    # their IDs in the owning test schemas before deleting cross-service IDs.
    user_ids = json.loads(
        fixture_shell(
            "user-service",
            "import os,json; from accounts.models import User; "
            "m=os.environ['PHASE8_MARKER']; "
            "print(json.dumps([str(v) for v in User.objects.filter(username__startswith=m).values_list('id',flat=True)]))",
        )
    )
    catalog = json.loads(
        fixture_shell(
            "book-service",
            "import os,json; from django.db.models import Q; from catalog.models import Book,Category; "
            "m=os.environ['PHASE8_MARKER']; "
            "c=list(Category.objects.filter(name__startswith=m).values_list('id',flat=True)); "
            "b=list(Book.objects.filter(Q(title__startswith=m)|Q(category_id__in=c)).values_list('id',flat=True)); "
            "print(json.dumps({'books':[str(v) for v in b],'categories':[str(v) for v in c]}))",
        )
    )
    book_ids = catalog["books"]
    category_ids = catalog["categories"]
    if book_ids or user_ids:
        fixture_shell(
            "borrow-service",
            "from django.db.models import Q; from borrowing.models import BorrowRecord,BorrowerLock; "
            f"BorrowRecord.objects.filter(Q(book_id__in={book_ids!r})|Q(user_id__in={user_ids!r})).delete(); "
            f"BorrowerLock.objects.filter(user_id__in={user_ids!r}).delete()",
        )
    if book_ids:
        fixture_shell(
            "book-service",
            "from catalog.models import Book,StockOperation; "
            f"StockOperation.objects.filter(book_id__in={book_ids!r}).delete(); "
            f"Book.objects.filter(pk__in={book_ids!r}).delete()",
        )
    if category_ids:
        fixture_shell(
            "book-service",
            "from catalog.models import Category; "
            f"Category.objects.filter(pk__in={category_ids!r}).delete()",
        )
    fixture_shell(
        "user-service",
        "import os; from accounts.models import User; User.objects.filter(username__startswith=os.environ['PHASE8_MARKER']).delete()",
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--hold",
        action="store_true",
        help="Keep fixtures/services until tmp/phase8-http/stop exists",
    )
    args = parser.parse_args()
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    stop = ARTIFACTS / "stop"
    stop.unlink(missing_ok=True)
    ids = {"users": [], "categories": [], "books": [], "borrows": []}
    processes, streams = [], []
    try:
        for name in NAMES[:3]:
            manage(name, "migrate", "--noinput", timeout=120)
        fixture_shell(
            "user-service",
            "import os; from accounts.models import User; m=os.environ['PHASE8_MARKER']; p=os.environ['PHASE8_PASSWORD']; User.objects.create_user(m+'_admin',m+'_admin@example.com',p,role='ADMIN')",
        )
        start_servers(processes, streams)
        fixture = verify_journeys(ids)
        if args.hold:
            destination = ARTIFACTS / "browser-fixture.json"
            destination.write_text(json.dumps(fixture, indent=2), encoding="utf-8")
            print(f"BROWSER_READY {destination}; create {stop} to finish", flush=True)
            while not stop.exists():
                if any(process.poll() is not None for process in processes):
                    raise RuntimeError(
                        "A stage 8 service exited during browser verification"
                    )
                time.sleep(1)
    finally:
        (ARTIFACTS / "browser-fixture.json").unlink(missing_ok=True)
        stop.unlink(missing_ok=True)
        for process in processes:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)
        for stream in streams:
            stream.close()
        cleanup(ids)
        print("Stage 8 isolated servers stopped and fixtures removed.", flush=True)


if __name__ == "__main__":
    main()
