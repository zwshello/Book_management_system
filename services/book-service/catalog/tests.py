import io
import json
import os
import subprocess
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.db import (
    IntegrityError,
    close_old_connections,
    connection,
    transaction,
)
from django.test import SimpleTestCase, TransactionTestCase, override_settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient, APITestCase

from .errors import ServiceUnavailable
from .models import Book, Category, StockOperation
from .user_client import current_authorization


class UserServiceConfigurationTests(SimpleTestCase):
    def test_user_service_url_is_required(self):
        env = os.environ.copy()
        env["USER_SERVICE_URL"] = ""
        result = subprocess.run(
            [sys.executable, "manage.py", "check"],
            cwd=Path(__file__).resolve().parent.parent,
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Configure a valid USER_SERVICE_URL", result.stderr)


KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
PUBLIC = (
    KEY.public_key()
    .public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    .decode()
)
JWT_SETTINGS = {**settings.SIMPLE_JWT, "VERIFYING_KEY": PUBLIC}
SUBJECT = str(uuid.uuid4())
SERVICE_TOKEN = "test-borrow-service-credential"
BASE = "/api/v1/"


def token(role="ADMIN", **changes):
    payload = {
        "sub": SUBJECT,
        "role": role,
        "token_type": "access",
        "jti": str(uuid.uuid4()),
        "iat": int(time.time()),
        "exp": int(time.time()) + 900,
        "iss": JWT_SETTINGS["ISSUER"],
        "aud": JWT_SETTINGS["AUDIENCE"],
    }
    payload.update(changes)
    return jwt.encode(payload, PRIVATE, algorithm="RS256")


def create_category(name="Computer"):
    return Category.objects.create(name=name, normalized_name=name.casefold())


def create_book(category, **changes):
    data = {
        "category": category,
        "title": "Python Basics",
        "author": "Alice",
        "isbn": "9780306406157",
        "total_copies": 3,
        "available_copies": 3,
    }
    data.update(changes)
    return Book.objects.create(**data)


@override_settings(SIMPLE_JWT=JWT_SETTINGS, BORROW_SERVICE_TOKEN=SERVICE_TOKEN)
class CatalogApiTests(APITestCase):
    def setUp(self):
        self.category = create_category()
        self.book = create_book(self.category)
        self.authorization = patch(
            "catalog.permissions.current_authorization",
            return_value={"role": "ADMIN"},
        )
        self.authorization.start()
        self.addCleanup(self.authorization.stop)
        self.archive_auth = patch(
            "catalog.views.current_authorization",
            return_value={"role": "ADMIN"},
        )
        self.archive_auth.start()
        self.addCleanup(self.archive_auth.stop)
        self.authorize()

    def authorize(self, role="ADMIN", **changes):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token(role, **changes))

    def detail(self):
        return BASE + f"books/{self.book.pk}"

    def new_book(self, **changes):
        data = {
            "title": "New Title",
            "author": "Bob",
            "isbn": "9780132350884",
            "category": str(self.category.pk),
            "total_copies": 2,
            "available_copies": 2,
        }
        data.update(changes)
        return self.client.post(BASE + "books", data, format="json")

    def test_mysql_isolated_database(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertEqual(connection.settings_dict["NAME"], "book_db_test")

    def test_internal_availability_provides_borrow_snapshot(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + SERVICE_TOKEN)
        response = self.client.get(f"/internal/v1/books/{self.book.pk}/availability")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Python Basics")
        self.assertEqual(response.data["isbn"], "9780306406157")

    def test_admin_creates_category(self):
        response = self.client.post(
            BASE + "categories",
            {"name": "  Science   Fiction  "},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["name"], "Science Fiction")

    def test_duplicate_normalized_category(self):
        self.assertEqual(
            self.client.post(
                BASE + "categories", {"name": " computer "}, format="json"
            ).status_code,
            400,
        )

    def test_category_read_update_delete(self):
        category = create_category("Unused")
        url = BASE + f"categories/{category.pk}"
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(
            self.client.patch(url, {"name": "Renamed"}, format="json").status_code,
            200,
        )
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_category_delete_referenced_rejected(self):
        self.assertEqual(
            self.client.delete(BASE + f"categories/{self.category.pk}").status_code,
            409,
        )
        self.client.delete(self.detail())
        self.assertEqual(
            self.client.delete(BASE + f"categories/{self.category.pk}").status_code,
            409,
        )

    def test_category_invalid_fields(self):
        for data in (
            {"name": " "},
            {"name": "x" * 101},
            {"name": "Valid", "id": str(uuid.uuid4())},
        ):
            self.assertEqual(
                self.client.post(BASE + "categories", data, format="json").status_code,
                400,
            )

    def test_admin_creates_book(self):
        response = self.new_book()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["available_copies"], 2)
        self.assertEqual(response.data["category_name"], "Computer")

    def test_initial_available_defaults_to_total(self):
        data = {
            "title": "Default Stock",
            "author": "Bob",
            "isbn": "9780132350884",
            "category": str(self.category.pk),
            "total_copies": 5,
        }
        response = self.client.post(BASE + "books", data, format="json")
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["available_copies"], 5)

    def test_ordinary_user_cannot_write(self):
        self.authorize("USER")
        self.assertEqual(self.new_book().status_code, 403)
        self.assertEqual(
            self.client.patch(
                self.detail(), {"title": "Changed"}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(self.client.delete(self.detail()).status_code, 403)
        self.assertEqual(
            self.client.post(
                BASE + "categories", {"name": "Denied"}, format="json"
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                BASE + f"categories/{self.category.pk}",
                {"name": "Denied"},
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(BASE + f"categories/{self.category.pk}").status_code,
            403,
        )

    def test_modify_book(self):
        response = self.client.patch(
            self.detail(),
            {"title": "Updated", "published_date": "2020-01-02"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.title, "Updated")

    def test_archive_book(self):
        self.assertEqual(self.client.delete(self.detail()).status_code, 204)
        self.book.refresh_from_db()
        self.assertEqual(self.book.status, "ARCHIVED")
        self.assertIsNotNone(self.book.archived_at)
        self.assertEqual(self.client.get(BASE + "books").data["count"], 0)
        self.assertEqual(self.client.get(self.detail()).status_code, 404)
        self.assertEqual(
            self.client.get(BASE + "books", {"status": "ARCHIVED"}).data["count"],
            1,
        )

    def test_ordinary_user_cannot_read_archived(self):
        self.client.delete(self.detail())
        self.authorize("USER")
        self.assertEqual(self.client.get(self.detail()).status_code, 404)
        self.assertEqual(
            self.client.get(BASE + "books", {"status": "ARCHIVED"}).status_code,
            403,
        )

    def test_status_edit_can_restore_archive(self):
        self.client.delete(self.detail())
        response = self.client.patch(self.detail(), {"status": "ACTIVE"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.book.refresh_from_db()
        self.assertIsNone(self.book.archived_at)

    def test_detail_query(self):
        self.authorize("USER")
        response = self.client.get(self.detail())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], "Python Basics")

    def test_title_fuzzy_query(self):
        self.assertEqual(
            self.client.get(BASE + "books", {"title": "PYTH"}).data["count"], 1
        )

    def test_author_fuzzy_and_exact_query(self):
        self.assertEqual(
            self.client.get(BASE + "books", {"author": "lic"}).data["count"], 1
        )
        self.assertEqual(
            self.client.get(BASE + "books", {"author_exact": "Alice"}).data["count"],
            1,
        )
        self.assertEqual(
            self.client.get(BASE + "books", {"author_exact": "lic"}).data["count"],
            0,
        )

    def test_title_exact_query(self):
        self.assertEqual(
            self.client.get(BASE + "books", {"title_exact": "Python Basics"}).data[
                "count"
            ],
            1,
        )
        self.assertEqual(
            self.client.get(BASE + "books", {"title_exact": "Python"}).data["count"],
            0,
        )

    def test_isbn_query_and_isbn10_conversion(self):
        response = self.client.get(BASE + "books", {"isbn": "0-306-40615-2"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["isbn"], "9780306406157")

    def test_category_filter(self):
        self.assertEqual(
            self.client.get(
                BASE + "books", {"category_id": str(self.category.pk)}
            ).data["count"],
            1,
        )
        self.assertEqual(
            self.client.get(BASE + "books", {"category_id": str(uuid.uuid4())}).data[
                "count"
            ],
            0,
        )

    def test_status_query(self):
        self.assertEqual(
            self.client.get(BASE + "books", {"status": "ACTIVE"}).data["count"],
            1,
        )
        self.assertEqual(
            self.client.get(BASE + "books", {"status": "ARCHIVED"}).data["count"],
            0,
        )

    def test_combined_query(self):
        create_book(
            self.category,
            title="Python Sold Out",
            isbn="9780132350884",
            available_copies=0,
        )
        values = {
            "title": "Python",
            "author": "Alice",
            "category_id": str(self.category.pk),
            "availability": "available",
        }
        response = self.client.get(BASE + "books", values)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Python Basics")

    def test_pagination_and_sorting(self):
        create_book(self.category, title="Zebra", isbn="9780132350884")
        one = self.client.get(BASE + "books", {"page_size": 1, "ordering": "title"})
        two = self.client.get(
            BASE + "books", {"page_size": 1, "page": 2, "ordering": "title"}
        )
        self.assertEqual(one.data["count"], 2)
        self.assertEqual(two.data["results"][0]["title"], "Zebra")

    def test_illegal_isbn(self):
        for isbn in (
            "bad",
            "9780306406158",
            "0306406153",
            "9770306406158",
            "",
        ):
            self.assertEqual(self.new_book(isbn=isbn).status_code, 400)

    def test_duplicate_isbn_and_alias(self):
        for isbn in ("9780306406157", "978-0-306-40615-7", "0306406152"):
            self.assertEqual(self.new_book(isbn=isbn).status_code, 400)

    def test_negative_stock(self):
        for values in ({"total_copies": -1}, {"available_copies": -1}):
            self.assertEqual(self.new_book(**values).status_code, 400)

    def test_available_exceeds_total(self):
        self.assertEqual(
            self.new_book(total_copies=1, available_copies=2).status_code, 400
        )

    def test_invalid_book_fields(self):
        for values in (
            {"title": " "},
            {"author": ""},
            {"status": "DISABLED"},
            {"category": str(uuid.uuid4())},
            {"published_date": "2026-02-30"},
            {"total_count": 3},
        ):
            self.assertEqual(self.new_book(**values).status_code, 400)

    def test_stock_edit_requires_dedicated_endpoint(self):
        self.assertEqual(
            self.client.patch(
                self.detail(), {"available_copies": 1}, format="json"
            ).status_code,
            400,
        )

    def test_stock_adjustment_preserves_occupied_copies(self):
        self.book.available_copies = 1
        self.book.save()
        url = self.detail() + "/stock-adjustments"
        self.assertEqual(
            self.client.post(url, {"total_copies": 1}, format="json").status_code,
            409,
        )
        response = self.client.post(url, {"total_copies": 4}, format="json")
        self.assertEqual(response.data["available_copies"], 2)
        self.assertEqual(
            self.client.post(url, {"total_copies": -1}, format="json").status_code,
            400,
        )

    def test_unauthenticated_access(self):
        self.client.credentials()
        for url in (BASE + "books", self.detail(), BASE + "categories"):
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_invalid_jwt_claims_and_signature(self):
        for changes in (
            {"exp": 1},
            {"sub": "bad"},
            {"role": "ROOT"},
            {"iss": "other"},
            {"aud": "other"},
            {"token_type": "refresh"},
        ):
            self.authorize(**changes)
            self.assertEqual(self.client.get(BASE + "books").status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer not-a-token")
        self.assertEqual(self.client.get(BASE + "books").status_code, 401)

    def test_current_role_demotion_blocks_stale_admin_token(self):
        with patch(
            "catalog.permissions.current_authorization",
            return_value={"role": "USER"},
        ):
            self.assertEqual(self.new_book().status_code, 403)
        self.assertEqual(Book.objects.count(), 1)

    def test_user_service_failure_blocks_write(self):
        with patch(
            "catalog.permissions.current_authorization",
            side_effect=ServiceUnavailable(),
        ):
            self.assertEqual(self.new_book().status_code, 503)
        self.assertEqual(Book.objects.count(), 1)

    def test_invalid_query_parameters(self):
        for values in (
            {"status": "BAD"},
            {"category_id": "bad"},
            {"isbn": "bad"},
            {"availability": "yes"},
            {"page": 0},
            {"page_size": 101},
            {"ordering": "isbn"},
            {"unknown": "x"},
        ):
            self.assertEqual(self.client.get(BASE + "books", values).status_code, 400)
        self.assertEqual(self.client.get(BASE + "books?page=1&page=2").status_code, 400)
        self.assertEqual(self.client.get(BASE + "books?page=99").status_code, 404)

    def test_error_envelope_and_invalid_id(self):
        response = self.client.get(BASE + "books/not-a-uuid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["request_id"], response["X-Request-ID"])
        self.assertEqual(
            self.client.get(BASE + f"books/{uuid.uuid4()}").status_code, 404
        )

    def test_database_stock_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Book.objects.filter(pk=self.book.pk).update(available_copies=99)


@override_settings(BORROW_SERVICE_TOKEN=SERVICE_TOKEN)
class StockApiTests(APITestCase):
    def setUp(self):
        self.category = create_category()
        self.book = create_book(self.category, total_copies=1, available_copies=1)
        self.borrow = uuid.uuid4()
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + SERVICE_TOKEN)

    def operate(self, kind="reservations", key=None, borrow=None):
        return self.client.post(
            f"/internal/v1/books/{self.book.pk}/{kind}",
            {"borrow_id": str(borrow or self.borrow)},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
        )

    def test_reserve_and_release(self):
        self.assertEqual(self.operate().status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)
        self.assertEqual(self.operate("releases").status_code, 200)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_idempotent_reservation_and_release(self):
        reserve, release = uuid.uuid4(), uuid.uuid4()
        first = self.operate(key=reserve)
        self.assertEqual(first.data, self.operate(key=reserve).data)
        first_release = self.operate("releases", key=release)
        self.assertEqual(first_release.data, self.operate("releases", key=release).data)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(StockOperation.objects.count(), 2)

    def test_failed_reservation_is_persisted_and_replayed(self):
        self.book.available_copies = 0
        self.book.save()
        key = uuid.uuid4()
        failed = self.operate(key=key)
        self.assertEqual(failed.status_code, 409)
        self.assertIs(failed.data["details"]["operation"]["success"], False)
        self.assertIsInstance(
            failed.data["details"]["operation"]["available_copies"], int
        )
        self.book.available_copies = 1
        self.book.save()
        self.assertEqual(self.operate(key=key).status_code, 409)
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(StockOperation.objects.count(), 1)

    def test_release_without_reservation_rejected(self):
        response = self.operate("releases")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "RESERVATION_NOT_FOUND")

    def test_same_key_payload_mismatch_rejected(self):
        key = uuid.uuid4()
        self.operate(key=key)
        self.assertEqual(self.operate(key=key, borrow=uuid.uuid4()).status_code, 409)

    def test_new_key_same_borrow_rejected(self):
        self.operate()
        self.assertEqual(self.operate().status_code, 409)

    def test_archived_book_can_release_but_not_reserve(self):
        self.operate()
        self.book.refresh_from_db()
        from django.utils import timezone

        self.book.status, self.book.archived_at = "ARCHIVED", timezone.now()
        self.book.save(update_fields=["status", "archived_at", "updated_at"])
        self.assertEqual(self.operate(borrow=uuid.uuid4()).status_code, 409)
        self.assertEqual(self.operate("releases").status_code, 200)

    def test_query_operation_after_response_loss(self):
        key = uuid.uuid4()
        original = self.operate(key=key)
        response = self.client.get(f"/internal/v1/books/operations/{key}")
        self.assertEqual(response.data, original.data)
        self.assertEqual(
            self.client.get(
                f"/internal/v1/books/operations/{uuid.uuid4()}"
            ).status_code,
            404,
        )

    def test_missing_idempotency_key_and_bad_input(self):
        url = f"/internal/v1/books/{self.book.pk}/reservations"
        self.assertEqual(
            self.client.post(
                url, {"borrow_id": str(self.borrow)}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                url,
                {"borrow_id": "bad"},
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            ).status_code,
            400,
        )

    def test_internal_api_rejects_user_token_and_missing_credential(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token())
        self.assertEqual(self.operate().status_code, 401)
        self.client.credentials()
        self.assertEqual(self.operate().status_code, 401)

    def test_availability(self):
        response = self.client.get(f"/internal/v1/books/{self.book.pk}/availability")
        self.assertTrue(response.data["available"])


@override_settings(BORROW_SERVICE_TOKEN=SERVICE_TOKEN)
class ConcurrentStockTests(TransactionTestCase):
    def test_last_copy_can_only_be_reserved_once(self):
        book = create_book(create_category(), total_copies=1, available_copies=1)

        def reserve(_):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(HTTP_AUTHORIZATION="Bearer " + SERVICE_TOKEN)
                return client.post(
                    f"/internal/v1/books/{book.pk}/reservations",
                    {"borrow_id": str(uuid.uuid4())},
                    format="json",
                    HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(reserve, range(2)))
        self.assertEqual(sorted(results), [200, 409])
        book.refresh_from_db()
        self.assertEqual(book.available_copies, 0)
        self.assertEqual(StockOperation.objects.count(), 2)


@override_settings(BOOK_SERVICE_TOKEN="test-book-credential")
class UserClientTests(SimpleTestCase):
    def test_current_authorization_success(self):
        with patch("catalog.user_client.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = json.dumps(
                {
                    "id": SUBJECT,
                    "role": "ADMIN",
                    "is_active": True,
                    "archived_at": None,
                }
            ).encode()
            self.assertEqual(current_authorization(SUBJECT, "access")["role"], "ADMIN")

    def test_dependency_unavailable(self):
        with patch("catalog.user_client.build_opener") as factory:
            factory.return_value.open.side_effect = URLError("offline")
            with self.assertRaises(ServiceUnavailable):
                current_authorization(SUBJECT, "access")

    def test_http_user_failure_and_service_mismatch(self):
        for code, exception in (
            ("UNAUTHENTICATED", AuthenticationFailed),
            ("INVALID_SERVICE_CREDENTIAL", ServiceUnavailable),
        ):
            with patch("catalog.user_client.build_opener") as factory:
                factory.return_value.open.side_effect = HTTPError(
                    "url",
                    401,
                    "Unauthorized",
                    None,
                    io.BytesIO(json.dumps({"code": code}).encode()),
                )
                with self.assertRaises(exception):
                    current_authorization(SUBJECT, "access")

    def test_malformed_authorization_response(self):
        with patch("catalog.user_client.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 200
            response.read.return_value = b"{}"
            with self.assertRaises(ServiceUnavailable):
                current_authorization(SUBJECT, "access")


@override_settings(STATISTICS_SERVICE_TOKEN="test-statistics-credential")
class BookSummaryTests(APITestCase):
    def setUp(self):
        self.category = create_category()
        create_book(self.category)
        create_book(
            self.category, isbn="9780132350884", available_copies=0, total_copies=2
        )
        archived = create_book(
            self.category, isbn="9780321125217", available_copies=5, total_copies=5
        )
        from django.utils import timezone

        archived.status = "ARCHIVED"
        archived.archived_at = timezone.now()
        archived.save(update_fields=["status", "archived_at"])
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-statistics-credential")

    def test_counts_active_titles_and_copies(self):
        response = self.client.get("/internal/v1/books/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            {"book_total": 2, "available_copies": 3, "available_titles": 1},
        )
        self.assertEqual(
            self.client.get("/internal/v1/books/summary?unexpected=1").status_code, 400
        )

    def test_user_jwt_cannot_read_internal_summary(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token())
        self.assertEqual(self.client.get("/internal/v1/books/summary").status_code, 401)
