import time
import uuid
from unittest.mock import patch

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from django.conf import settings
from django.test import override_settings
from rest_framework.test import APIClient, APISimpleTestCase

from .clients import book_summary, borrow_summary, user_summary
from .errors import ServiceUnavailable

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
PRIVATE = KEY.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
PUBLIC = KEY.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
JWT_SETTINGS = {**settings.SIMPLE_JWT, "VERIFYING_KEY": PUBLIC}
SUBJECT = uuid.uuid4()
URL = "/api/v1/statistics/overview"


def token(role="ADMIN"):
    now = int(time.time())
    return jwt.encode({"sub": str(SUBJECT), "role": role, "token_type": "access", "jti": str(uuid.uuid4()), "iat": now, "exp": now + 900, "iss": JWT_SETTINGS["ISSUER"], "aud": JWT_SETTINGS["AUDIENCE"]}, PRIVATE, algorithm="RS256")


@override_settings(SIMPLE_JWT=JWT_SETTINGS, STATISTICS_SERVICE_TOKEN="test-statistics-credential")
class OverviewTests(APISimpleTestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token())
        self.authorization = patch("analytics.views.user_authorization", return_value={"id": str(SUBJECT), "role": "ADMIN", "is_active": True, "archived_at": None})
        self.users = patch("analytics.views.user_summary", return_value={"total_users": 7})
        self.books = patch("analytics.views.book_summary", return_value={"book_total": 5, "available_titles": 3, "available_copies": 9})
        self.borrows = patch("analytics.views.borrow_summary", return_value={"borrowed_copies": 4, "current_borrows": 3})
        self.calls = [item.start() for item in (self.authorization, self.users, self.books, self.borrows)]
        for item in (self.authorization, self.users, self.books, self.borrows):
            self.addCleanup(item.stop)

    def test_five_metrics_and_echarts_format(self):
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["user_total"], 7)
        self.assertEqual(response.data["book_total"], 5)
        self.assertEqual(response.data["available_copies"], 9)
        self.assertEqual(response.data["available_book_titles"], 3)
        self.assertEqual(response.data["borrowed_copies"], 4)
        self.assertEqual(response.data["current_borrows"], 3)
        self.assertEqual(len(response.data["chart"]["labels"]), 5)
        self.assertEqual(response.data["chart"]["values"], [7, 5, 9, 4, 3])
        self.assertEqual(response["X-Request-ID"], response.wsgi_request.request_id)
        self.assertEqual(self.calls[1].call_count, 1)
        self.assertEqual(self.calls[2].call_count, 1)
        self.assertEqual(self.calls[3].call_count, 1)

    def test_ordinary_and_unauthenticated_denied(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + token("USER"))
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.calls[1].call_count, 0)
        self.client.credentials()
        self.assertEqual(self.client.get(URL).status_code, 401)

    def test_stale_admin_role_denied(self):
        self.calls[0].return_value = {"role": "USER"}
        self.assertEqual(self.client.get(URL).status_code, 403)
        self.assertEqual(self.calls[1].call_count, 0)

    def test_upstream_unavailable_returns_503(self):
        self.calls[2].side_effect = ServiceUnavailable("book offline")
        response = self.client.get(URL)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.data["code"], "SERVICE_UNAVAILABLE")

    def test_rejects_parameters_and_removed_endpoints(self):
        self.assertEqual(self.client.get(URL + "?limit=5").status_code, 400)
        for path in ("categories", "popular-books", "monthly-borrows", "users", "me"):
            self.assertEqual(self.client.get("/api/v1/statistics/" + path).status_code, 404)


@override_settings(STATISTICS_SERVICE_TOKEN="test-statistics-credential")
class ClientValidationTests(APISimpleTestCase):
    def test_rejects_malformed_and_inconsistent_summaries(self):
        with patch("analytics.clients.get_json", return_value={"total_users": True}):
            with self.assertRaises(ServiceUnavailable):
                user_summary()
        with patch("analytics.clients.get_json", return_value={"book_total": 1, "available_titles": 2, "available_copies": 3}):
            with self.assertRaises(ServiceUnavailable):
                book_summary()
        with patch("analytics.clients.get_json", return_value={"borrowed_copies": 1, "current_borrows": 2}):
            with self.assertRaises(ServiceUnavailable):
                borrow_summary()
