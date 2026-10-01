import uuid

from django.test import override_settings
from rest_framework.test import APITestCase

from .models import User
from .serializers import LoginSerializer


@override_settings(BOOK_SERVICE_TOKEN="test-book-service-credential")
class BookAuthorizationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "book_admin",
            "bookadmin@example.com",
            "Test!Library-2026",
            role="ADMIN",
        )
        self.access = str(LoginSerializer.get_token(self.user).access_token)
        self.url = f"/internal/v1/users/{self.user.pk}/authorization"
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer test-book-service-credential"
        )

    def get(self, **headers):
        return self.client.get(
            self.url, HTTP_X_USER_ACCESS_TOKEN=self.access, **headers
        )

    def test_authorization_returns_current_role(self):
        self.assertEqual(self.get().data["role"], "ADMIN")
        self.user.role = "USER"
        self.user.save()
        self.assertEqual(self.get().data["role"], "USER")

    def test_rejects_user_jwt_as_service_credential(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.access)
        response = self.get()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["code"], "INVALID_SERVICE_CREDENTIAL")

    def test_missing_or_wrong_user_token(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)
        self.assertEqual(
            self.client.get(self.url, HTTP_X_USER_ACCESS_TOKEN="bad").status_code,
            401,
        )

    def test_disabled_user_rejected(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.get().status_code, 401)

    def test_password_change_rejects_old_token(self):
        self.user.set_password("Changed!Library-2026")
        self.user.save()
        self.assertEqual(self.get().status_code, 401)

    def test_subject_mismatch_rejected(self):
        response = self.client.get(
            f"/internal/v1/users/{uuid.uuid4()}/authorization",
            HTTP_X_USER_ACCESS_TOKEN=self.access,
        )
        self.assertEqual(response.status_code, 403)


@override_settings(BORROW_SERVICE_TOKEN="test-borrow-service-credential")
class BorrowEligibilityTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            "borrow_reader", "borrow@example.com", "Test!Library-2026"
        )
        self.access = str(LoginSerializer.get_token(self.user).access_token)
        self.url = f"/internal/v1/users/{self.user.pk}/eligibility"
        self.client.credentials(
            HTTP_AUTHORIZATION="Bearer test-borrow-service-credential"
        )

    def get(self, *, access=None):
        return self.client.get(self.url, HTTP_X_USER_ACCESS_TOKEN=access or self.access)

    def test_current_user_and_role(self):
        self.assertEqual(self.get().data["username"], "borrow_reader")
        self.user.role = "ADMIN"
        self.user.save()
        self.assertEqual(self.get().data["role"], "ADMIN")

    def test_missing_user_is_not_found(self):
        self.user.delete()
        self.assertEqual(self.get().status_code, 404)

    def test_disabled_user_and_old_password_token(self):
        self.user.is_active = False
        self.user.save()
        self.assertEqual(self.get().status_code, 401)
        self.user.is_active = True
        self.user.set_password("New!Library-2026")
        self.user.save()
        self.assertEqual(self.get().status_code, 401)

    def test_user_jwt_cannot_replace_service_identity(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + self.access)
        self.assertEqual(self.get().status_code, 401)

    def test_subject_mismatch_and_invalid_token(self):
        self.assertEqual(self.get(access="bad").status_code, 401)
        self.assertEqual(
            self.client.get(
                f"/internal/v1/users/{uuid.uuid4()}/eligibility",
                HTTP_X_USER_ACCESS_TOKEN=self.access,
            ).status_code,
            403,
        )


@override_settings(STATISTICS_SERVICE_TOKEN="test-statistics-credential")
class UserSummaryTests(APITestCase):
    def setUp(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer test-statistics-credential")

    def test_counts_unarchived_users_including_disabled(self):
        User.objects.create_user("stats_one", "stats1@example.com", "Test!Library-2026")
        User.objects.create_user("stats_two", "stats2@example.com", "Test!Library-2026", is_active=False)
        archived = User.objects.create_user("stats_old", "stats3@example.com", "Test!Library-2026")
        from django.utils import timezone

        archived.archived_at = timezone.now()
        archived.save()
        self.assertEqual(self.client.get("/internal/v1/users/summary").data["total_users"], 2)

    def test_user_jwt_cannot_read_internal_summary(self):
        user = User.objects.create_user("stats_reader", "statsreader@example.com", "Test!Library-2026")
        self.client.credentials(HTTP_AUTHORIZATION="Bearer " + str(LoginSerializer.get_token(user).access_token))
        self.assertEqual(self.client.get("/internal/v1/users/summary").status_code, 401)
