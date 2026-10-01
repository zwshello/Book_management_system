import io
import time
import uuid
from datetime import timedelta
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.core.management import call_command
from django.db import DatabaseError, connection
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import NotFound
from rest_framework.test import APITestCase

from .errors import Conflict, ServiceUnavailable
from .models import BorrowRecord

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
)
PUBLIC = (
    KEY.public_key()
    .public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    .decode()
)
JWT_SETTINGS = {**settings.SIMPLE_JWT, "VERIFYING_KEY": PUBLIC}


def token(subject, role="USER"):
    now = int(time.time())
    return jwt.encode(
        {
            "sub": str(subject),
            "role": role,
            "token_type": "access",
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 900,
            "iss": JWT_SETTINGS["ISSUER"],
            "aud": JWT_SETTINGS["AUDIENCE"],
        },
        PRIVATE,
        algorithm="RS256",
    )


@override_settings(SIMPLE_JWT=JWT_SETTINGS, MAX_ACTIVE_BORROWS=5, BORROW_DAYS=30)
class BorrowApiTests(APITestCase):
    def setUp(self):
        self.user_id = uuid.uuid4()
        self.other_id = uuid.uuid4()
        self.book_id = uuid.uuid4()
        self.stock = 3
        self.operations = {}
        self.current_role = "USER"
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token(self.user_id))
        self.user_patch = patch(
            "borrowing.views.user_eligibility", side_effect=self.user_eligibility
        )
        self.book_patch = patch(
            "borrowing.views.book_availability", side_effect=self.book_availability
        )
        self.get_patch = patch(
            "borrowing.workflow.operation_result", side_effect=self.operation_result
        )
        self.put_patch = patch(
            "borrowing.workflow.execute_stock", side_effect=self.execute_stock
        )
        for item in (self.user_patch, self.book_patch, self.get_patch, self.put_patch):
            item.start()
            self.addCleanup(item.stop)

    def user_eligibility(self, subject, access):
        if subject == self.other_id:
            raise NotFound("用户不存在。")
        return {
            "id": str(subject),
            "username": "reader",
            "role": self.current_role,
            "is_active": True,
            "can_borrow": True,
        }

    def book_availability(self, book_id):
        if book_id != self.book_id:
            raise NotFound("图书不存在。")
        if self.stock <= 0:
            raise Conflict("图书库存不足。")
        return {
            "id": str(book_id),
            "title": "Python",
            "isbn": "9780306406157",
            "available_copies": self.stock,
            "total_copies": 3,
            "status": "ACTIVE",
            "available": self.stock > 0,
        }

    def operation_result(self, record, kind):
        key = record.reservation_key if kind == "RESERVE" else record.release_key
        return self.operations.get(key)

    def execute_stock(self, record, kind):
        key = record.reservation_key if kind == "RESERVE" else record.release_key
        if key in self.operations:
            return self.operations[key]
        code = "OK"
        if kind == "RESERVE":
            if self.stock <= 0:
                code = "OUT_OF_STOCK"
            else:
                self.stock -= 1
        else:
            if (
                record.reservation_key not in self.operations
                or not self.operations[record.reservation_key]["success"]
            ):
                code = "RESERVATION_NOT_FOUND"
            else:
                self.stock += 1
        result = {
            "success": code == "OK",
            "code": code,
            "operation_key": str(key),
            "borrow_id": str(record.pk),
            "book_id": str(record.book_id),
            "kind": kind,
            "total_copies": 3,
            "available_copies": self.stock,
        }
        self.operations[key] = result
        return result

    def borrow(self, key=None, book_id=None):
        return self.client.post(
            "/api/v1/borrows",
            {"book_id": str(book_id or self.book_id)},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
        )

    def return_book(self, borrow_id, key=None):
        return self.client.post(
            f"/api/v1/borrows/{borrow_id}/return",
            {},
            format="json",
            HTTP_IDEMPOTENCY_KEY=str(key or uuid.uuid4()),
        )

    def admin(self):
        self.current_role = "ADMIN"
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer " + token(self.user_id, "ADMIN")
        )

    def test_uses_isolated_mysql(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertEqual(connection.settings_dict["NAME"], "borrow_db_test")

    def test_normal_borrow_and_idempotent_repeat(self):
        key = uuid.uuid4()
        first = self.borrow(key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(first.data["status"], "ACTIVE")
        self.assertEqual(first.data["display_status"], "ACTIVE")
        self.assertEqual(self.stock, 2)
        self.assertEqual(self.borrow(key).status_code, 200)
        self.assertEqual(BorrowRecord.objects.count(), 1)
        self.assertEqual(len(self.operations), 1)
        self.assertAlmostEqual(
            (
                BorrowRecord.objects.get().due_at
                - BorrowRecord.objects.get().borrowed_at
            ).days,
            30,
        )

    def test_normal_return_and_repeated_return(self):
        record = self.borrow().data
        key = uuid.uuid4()
        response = self.return_book(record["id"], key)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "RETURNED")
        self.assertEqual(self.stock, 3)
        self.assertEqual(self.return_book(record["id"], key).status_code, 200)
        self.assertEqual(self.stock, 3)

    def test_book_missing_and_unavailable(self):
        self.assertEqual(self.borrow(book_id=uuid.uuid4()).status_code, 404)
        self.assertEqual(BorrowRecord.objects.count(), 0)
        self.stock = 0
        self.assertEqual(self.borrow().status_code, 409)
        self.assertEqual(BorrowRecord.objects.count(), 0)

    def test_atomic_stock_conflict_marks_failed(self):
        self.stock = 0
        with patch(
            "borrowing.views.book_availability",
            return_value={"title": "Python", "isbn": "9780306406157"},
        ):
            response = self.borrow()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.data["code"], "OUT_OF_STOCK")
        self.assertEqual(BorrowRecord.objects.get().status, "FAILED")
        self.assertEqual(self.stock, 0)

    def test_user_missing_and_unavailable(self):
        with patch(
            "borrowing.views.user_eligibility", side_effect=NotFound("用户不存在")
        ):
            self.assertEqual(self.borrow().status_code, 404)
        with patch(
            "borrowing.views.user_eligibility", side_effect=ServiceUnavailable("超时")
        ):
            self.assertEqual(self.borrow().status_code, 503)
        self.assertEqual(BorrowRecord.objects.count(), 0)

    def test_book_service_unavailable_before_intent(self):
        with patch(
            "borrowing.views.book_availability", side_effect=ServiceUnavailable("超时")
        ):
            self.assertEqual(self.borrow().status_code, 503)
        self.assertEqual(BorrowRecord.objects.count(), 0)

    def test_unauthenticated_and_invalid_input(self):
        self.client.credentials()
        self.assertEqual(self.borrow().status_code, 401)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token(self.user_id))
        self.assertEqual(
            self.client.post(
                "/api/v1/borrows", {"book_id": "bad"}, format="json"
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/borrows",
                {"book_id": str(self.book_id), "status": "ACTIVE"},
                format="json",
                HTTP_IDEMPOTENCY_KEY=str(uuid.uuid4()),
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/borrows",
                {"book_id": str(self.book_id)},
                format="json",
                HTTP_IDEMPOTENCY_KEY="bad",
            ).status_code,
            400,
        )

    def test_private_queries_and_admin_listing(self):
        my_record = self.borrow().data
        other = BorrowRecord.objects.create(
            request_key=uuid.uuid4(),
            user_id=self.other_id,
            book_id=self.book_id,
            username_snapshot="other",
            book_title_snapshot="Python",
            isbn_snapshot="9780306406157",
            borrow_days=30,
        )
        mine = self.client.get(
            "/api/v1/borrows/me", {"status": "ACTIVE", "page_size": 1}
        )
        self.assertEqual(mine.data["count"], 1)
        self.assertEqual(mine.data["results"][0]["id"], my_record["id"])
        self.assertEqual(
            self.client.get(
                "/api/v1/borrows/me", {"user_id": str(self.other_id)}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/borrows/{other.pk}").status_code, 403
        )
        self.assertEqual(self.client.get("/api/v1/borrows").status_code, 403)
        self.admin()
        self.assertEqual(self.client.get("/api/v1/borrows").data["count"], 2)
        self.assertEqual(
            self.client.get(
                "/api/v1/borrows", {"user_id": str(self.other_id), "status": "PENDING"}
            ).data["count"],
            1,
        )
        self.assertEqual(
            self.client.get(f"/api/v1/borrows/{other.pk}").status_code, 200
        )

    def test_stale_admin_role_denied(self):
        self.admin()
        self.current_role = "USER"
        self.assertEqual(self.client.get("/api/v1/borrows").status_code, 403)

    def test_cannot_return_other_users_record_or_missing_record(self):
        other = BorrowRecord.objects.create(
            request_key=uuid.uuid4(),
            user_id=self.other_id,
            book_id=self.book_id,
            username_snapshot="other",
            book_title_snapshot="Python",
            isbn_snapshot="9780306406157",
            borrow_days=30,
            status="ACTIVE",
            borrowed_at=timezone.now(),
            due_at=timezone.now() + timedelta(days=30),
        )
        self.assertEqual(self.return_book(other.pk).status_code, 403)
        other.refresh_from_db()
        self.assertEqual(other.status, "ACTIVE")
        self.assertEqual(self.stock, 3)
        self.assertEqual(self.return_book(uuid.uuid4()).status_code, 404)

    def test_pending_reserve_response_loss_recovered_with_same_key(self):
        original = self.execute_stock
        calls = []

        def lose_response(record, kind):
            result = original(record, kind)
            calls.append(result)
            raise ServiceUnavailable("响应丢失")

        with patch("borrowing.workflow.execute_stock", side_effect=lose_response):
            key = uuid.uuid4()
            response = self.borrow(key)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(BorrowRecord.objects.get().status, "PENDING")
        self.assertEqual(self.stock, 2)
        self.assertEqual(self.borrow(key).status_code, 200)
        self.assertEqual(BorrowRecord.objects.get().status, "ACTIVE")
        self.assertEqual(len(self.operations), 1)

    def test_pending_return_response_loss_recovered(self):
        record = self.borrow().data
        original = self.execute_stock

        def lose_response(item, kind):
            original(item, kind)
            raise ServiceUnavailable("响应丢失")

        with patch("borrowing.workflow.execute_stock", side_effect=lose_response):
            key = uuid.uuid4()
            response = self.return_book(record["id"], key)
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.stock, 3)
        self.assertEqual(self.return_book(record["id"], key).status_code, 200)
        self.assertEqual(self.stock, 3)

    def test_reconcile_command_completes_unknown_reservation(self):
        original = self.execute_stock

        def lose_response(record, kind):
            original(record, kind)
            raise ServiceUnavailable("response lost")

        with patch("borrowing.workflow.execute_stock", side_effect=lose_response):
            self.assertEqual(self.borrow().status_code, 202)
        output = io.StringIO()
        call_command("reconcile_borrows", min_age=0, stdout=output)
        self.assertIn("Checked 1 pending", output.getvalue())
        self.assertEqual(BorrowRecord.objects.get().status, "ACTIVE")
        self.assertEqual(self.stock, 2)

    def test_current_admin_can_return_other_users_record(self):
        borrowed = timezone.now()
        record = BorrowRecord.objects.create(
            request_key=uuid.uuid4(),
            user_id=self.other_id,
            book_id=self.book_id,
            username_snapshot="other",
            book_title_snapshot="Python",
            isbn_snapshot="9780306406157",
            borrow_days=30,
            status="ACTIVE",
            borrowed_at=borrowed,
            due_at=borrowed + timedelta(days=30),
        )
        self.stock = 2
        self.operations[record.reservation_key] = {
            "success": True,
            "code": "OK",
            "operation_key": str(record.reservation_key),
            "borrow_id": str(record.pk),
            "book_id": str(self.book_id),
            "kind": "RESERVE",
            "total_copies": 3,
            "available_copies": 2,
        }
        self.admin()
        self.assertEqual(self.return_book(record.pk).status_code, 200)
        self.assertEqual(self.stock, 3)
        record.refresh_from_db()
        self.assertEqual(record.status, "RETURNED")

    def test_database_finalization_failure_recovered(self):
        from .workflow import advance

        key = uuid.uuid4()
        user = self.user_eligibility(self.user_id, "token")
        book = self.book_availability(self.book_id)
        from .workflow import create_intent

        record, _ = create_intent(self.user_id, self.book_id, key, user, book, "test")
        with patch(
            "borrowing.workflow._save", side_effect=DatabaseError("save failed")
        ):
            with self.assertRaises(DatabaseError):
                advance(record.pk)
        record.refresh_from_db()
        self.assertEqual(record.status, "PENDING")
        self.assertEqual(self.stock, 2)
        self.assertEqual(advance(record.pk).status, "ACTIVE")
        self.assertEqual(self.stock, 2)

    def test_explicit_compensation_releases_once(self):
        original = self.execute_stock
        with patch(
            "borrowing.workflow.execute_stock",
            side_effect=lambda record, kind: (
                (_ for _ in ()).throw(ServiceUnavailable("lost"))
                if kind == "RESERVE"
                else original(record, kind)
            ),
        ):
            pending = self.borrow()
        self.assertEqual(pending.status_code, 202)
        record = BorrowRecord.objects.get()
        output = io.StringIO()
        call_command("reconcile_borrows", cancel_pending=str(record.pk), stdout=output)
        record.refresh_from_db()
        self.assertEqual(record.status, "FAILED")
        self.assertEqual(record.failure_code, "CANCELLED_COMPENSATED")
        self.assertEqual(self.stock, 3)
        self.assertEqual(len(self.operations), 2)

    def test_borrow_limit_counts_pending_and_active(self):
        for i in range(5):
            BorrowRecord.objects.create(
                request_key=uuid.uuid4(),
                user_id=self.user_id,
                book_id=uuid.uuid4(),
                username_snapshot="reader",
                book_title_snapshot="book",
                isbn_snapshot="9780306406157",
                borrow_days=30,
            )
        self.assertEqual(self.borrow().status_code, 409)
        self.assertEqual(BorrowRecord.objects.count(), 5)

    def test_overdue_query_and_admin_archive_terminal_only(self):
        first = self.borrow().data
        self.assertEqual(
            self.client.get("/api/v1/borrows/me", {"status": "OVERDUE"}).data["count"],
            0,
        )
        self.admin()
        detail = f"/api/v1/borrows/{first['id']}"
        self.assertEqual(self.client.delete(detail).status_code, 409)
        extended = timezone.now() + timedelta(days=40)
        self.assertEqual(
            self.client.patch(
                detail, {"due_at": extended.isoformat()}, format="json"
            ).status_code,
            200,
        )
        BorrowRecord.objects.filter(pk=first["id"]).update(
            borrowed_at=timezone.now() - timedelta(days=40),
            due_at=timezone.now() - timedelta(days=1),
        )
        self.assertEqual(
            self.client.get("/api/v1/borrows", {"status": "OVERDUE"}).data["count"], 1
        )
        self.assertEqual(self.client.get(detail).data["display_status"], "OVERDUE")
        self.assertEqual(self.return_book(first["id"]).status_code, 200)
        self.assertEqual(self.client.delete(detail).status_code, 204)
        self.assertEqual(self.client.get("/api/v1/borrows").data["count"], 0)
        self.assertEqual(
            self.client.get("/api/v1/borrows", {"include_archived": "true"}).data[
                "count"
            ],
            1,
        )

    def test_query_validation_dates_page_and_role_boundary(self):
        self.borrow()
        self.admin()
        for params in (
            {"page": "0"},
            {"page_size": "101"},
            {"status": "WRONG"},
            {"created_from": "2026-10-01", "created_to": "2026-09-01"},
            {"unknown": "x"},
        ):
            self.assertEqual(
                self.client.get("/api/v1/borrows", params).status_code, 400
            )
        self.assertEqual(
            self.client.get("/api/v1/borrows", {"page": 2}).status_code, 404
        )
        self.assertEqual(
            self.client.get(
                "/api/v1/borrows", {"created_from": timezone.localdate().isoformat()}
            ).data["count"],
            1,
        )


@override_settings(STATISTICS_SERVICE_TOKEN="test-statistics-credential")
class BorrowSummaryTests(APITestCase):
    def setUp(self):
        now = timezone.now()
        fields = {"user_id": uuid.uuid4(), "book_id": uuid.uuid4(), "username_snapshot": "reader", "book_title_snapshot": "Python", "isbn_snapshot": "9780306406157", "borrow_days": 30}
        BorrowRecord.objects.create(request_key=uuid.uuid4(), status="ACTIVE", borrowed_at=now, due_at=now + timedelta(days=30), **fields)
        BorrowRecord.objects.create(request_key=uuid.uuid4(), status="RETURN_PENDING", borrowed_at=now, due_at=now + timedelta(days=30), release_key=uuid.uuid4(), **fields)
        BorrowRecord.objects.create(request_key=uuid.uuid4(), **fields)
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-statistics-credential")

    def test_counts_current_and_occupied_without_pending(self):
        response = self.client.get("/internal/v1/borrows/summary")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"borrowed_copies": 2, "current_borrows": 1})
        self.assertEqual(self.client.get("/internal/v1/borrows/summary?section=popular").status_code, 400)

    def test_user_jwt_cannot_read_internal_summary(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token(uuid.uuid4()))
        self.assertEqual(self.client.get("/internal/v1/borrows/summary").status_code, 401)
