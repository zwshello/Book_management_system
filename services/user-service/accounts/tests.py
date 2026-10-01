import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import jwt
from django.conf import settings
from django.db import close_old_connections, connection
from django.test import TransactionTestCase
from rest_framework.test import APIClient, APITestCase
from rest_framework_simplejwt.tokens import AccessToken

from .models import AdministrationLock, User
from .serializers import LoginSerializer

PASSWORD = "Library!Test-2026"
BASE = "/api/v1/"


class UserApiTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_user(
            "administrator",
            "admin@example.com",
            PASSWORD,
            role="ADMIN",
        )
        cls.user = User.objects.create_user(
            "reader", "reader@example.com", PASSWORD
        )

    def authorize(self, user=None):
        token = LoginSerializer.get_token(user or self.user)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        return token

    def register(self, **changes):
        data = {
            "username": "new_reader",
            "email": "new@example.com",
            "password": PASSWORD,
        }
        data.update(changes)
        return self.client.post(BASE + "auth/register", data, format="json")

    def detail(self, user=None):
        return BASE + f"users/{(user or self.user).pk}"

    def test_mysql_is_used_in_isolated_test_database(self):
        self.assertEqual(connection.vendor, "mysql")
        self.assertEqual(connection.settings_dict["NAME"], "user_db_test")

    def test_registration_hashes_password_and_returns_user(self):
        response = self.register()
        self.assertEqual(response.status_code, 201)
        user = User.objects.get(username="new_reader")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertNotEqual(user.password, PASSWORD)
        self.assertEqual(response.data["role"], "USER")
        self.assertTrue(response.data["is_active"])
        self.assertNotIn("password", response.data)
        self.assertIsInstance(user.pk, uuid.UUID)

    def test_duplicate_username(self):
        self.assertEqual(self.register(username="READER").status_code, 400)

    def test_invalid_email(self):
        self.assertEqual(self.register(email="invalid-email").status_code, 400)

    def test_normalized_email_unique(self):
        self.assertEqual(
            self.register(email="READER@example.com").status_code, 400
        )

    def test_email_normalization(self):
        response = self.register(email="New@EXAMPLE.COM")
        self.assertEqual(response.data["email"], "new@example.com")

    def test_invalid_password_rules(self):
        for password in ("short", "123456789", "password", "new_reader"):
            with self.subTest(password=password):
                self.assertEqual(
                    self.register(password=password).status_code, 400
                )

    def test_username_required_and_length(self):
        for username in ("", "   ", "ab", "x" * 151):
            with self.subTest(username=username):
                self.assertEqual(
                    self.register(username=username).status_code, 400
                )

    def test_registration_rejects_privileged_fields(self):
        for changes in (
            {"role": "ADMIN"},
            {"is_active": False},
            {"is_superuser": True},
        ):
            self.assertEqual(self.register(**changes).status_code, 400)
        self.assertFalse(User.objects.filter(username="new_reader").exists())

    def test_login_and_rsa_claims(self):
        response = self.client.post(
            BASE + "auth/login",
            {
                "username": "READER",
                "password": PASSWORD,
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.data
        claims = jwt.decode(
            data["access"],
            settings.JWT_PUBLIC_KEY,
            algorithms=["RS256"],
            issuer="library-user-service",
            audience="library-services",
        )
        self.assertEqual(claims["sub"], str(self.user.pk))
        self.assertEqual(claims["role"], "USER")
        self.assertEqual(claims["token_type"], "access")
        self.assertIn("refresh", data)
        self.assertNotIn("password", data["user"])

    def test_wrong_login_password(self):
        response = self.client.post(
            BASE + "auth/login",
            {
                "username": "reader",
                "password": "wrong",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_unauthenticated_protected_endpoints(self):
        for url in (BASE + "users/me", BASE + "users", self.detail()):
            self.assertEqual(self.client.get(url).status_code, 401)

    def test_error_envelope_and_request_id(self):
        response = self.register(email="bad")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["code"], "VALIDATION_ERROR")
        self.assertIn("email", response.data["details"])
        self.assertEqual(response.data["request_id"], response["X-Request-ID"])

    def test_get_own_profile(self):
        self.authorize()
        response = self.client.get(BASE + "users/me")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(self.user.pk))

    def test_edit_own_profile(self):
        self.authorize()
        response = self.client.patch(
            BASE + "users/me",
            {
                "email": "Updated@Example.com",
                "display_name": "读者",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["email"], "updated@example.com")

    def test_profile_rejects_invalid_or_duplicate_email(self):
        self.authorize()
        for email in ("bad", "admin@example.com"):
            self.assertEqual(
                self.client.patch(
                    BASE + "users/me",
                    {
                        "email": email,
                    },
                    format="json",
                ).status_code,
                400,
            )

    def test_user_cannot_promote_or_disable_self(self):
        self.authorize()
        for changes in (
            {"role": "ADMIN"},
            {"is_active": False},
            {"username": "renamed"},
        ):
            self.assertEqual(
                self.client.patch(
                    BASE + "users/me",
                    changes,
                    format="json",
                ).status_code,
                400,
            )
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "USER")
        self.assertTrue(self.user.is_active)

    def test_user_cannot_access_admin_operations(self):
        self.authorize()
        self.assertEqual(self.client.get(BASE + "users").status_code, 403)
        self.assertEqual(
            self.client.get(self.detail(self.admin)).status_code, 403
        )
        self.assertEqual(
            self.client.post(
                BASE + "users",
                {
                    "username": "evil_admin",
                    "email": "evil@example.com",
                    "password": PASSWORD,
                    "role": "ADMIN",
                },
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.patch(
                self.detail(self.admin),
                {
                    "role": "USER",
                },
                format="json",
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(self.detail(self.admin)).status_code, 403
        )

    def test_admin_list_and_detail(self):
        self.authorize(self.admin)
        response = self.client.get(BASE + "users")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(self.client.get(self.detail()).status_code, 200)

    def test_admin_creates_user_and_admin(self):
        self.authorize(self.admin)
        for role in ("USER", "ADMIN"):
            response = self.client.post(
                BASE + "users",
                {
                    "username": "created_" + role.lower(),
                    "email": "created_" + role.lower() + "@example.com",
                    "password": PASSWORD,
                    "role": role,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 201)
            created = User.objects.get(pk=response.data["id"])
            self.assertEqual(created.role, role)
            self.assertTrue(created.check_password(PASSWORD))

    def test_admin_updates_user_and_password(self):
        self.authorize(self.admin)
        response = self.client.patch(
            self.detail(),
            {
                "display_name": "编辑后",
                "role": "ADMIN",
                "password": "New!SecurePass-2026",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "ADMIN")
        self.assertTrue(self.user.check_password("New!SecurePass-2026"))

    def test_admin_invalid_input_does_not_change_data(self):
        self.authorize(self.admin)
        for changes in (
            {"role": "ROOT"},
            {"is_superuser": True},
            {"email": "bad"},
            {"username": "administrator"},
            {"password": "short"},
        ):
            self.assertEqual(
                self.client.patch(
                    self.detail(),
                    changes,
                    format="json",
                ).status_code,
                400,
            )
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "USER")

    def test_disable_rejects_old_access_refresh_and_login(self):
        token = self.authorize()
        self.authorize(self.admin)
        self.assertEqual(
            self.client.patch(
                self.detail(),
                {
                    "is_active": False,
                },
                format="json",
            ).status_code,
            200,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        self.assertEqual(self.client.get(BASE + "users/me").status_code, 401)
        self.assertEqual(
            self.client.post(
                BASE + "auth/refresh",
                {
                    "refresh": str(token),
                },
                format="json",
            ).status_code,
            401,
        )
        self.assertEqual(
            self.client.post(
                BASE + "auth/login",
                {
                    "username": "reader",
                    "password": PASSWORD,
                },
                format="json",
            ).status_code,
            401,
        )

    def test_admin_reenable_user(self):
        self.user.is_active = False
        self.user.save()
        self.authorize(self.admin)
        self.assertEqual(
            self.client.patch(
                self.detail(),
                {
                    "is_active": True,
                },
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(
            self.client.post(
                BASE + "auth/login",
                {
                    "username": "reader",
                    "password": PASSWORD,
                },
                format="json",
            ).status_code,
            200,
        )

    def test_admin_delete_archives_and_preserves_id(self):
        token = self.authorize()
        self.authorize(self.admin)
        self.assertEqual(self.client.delete(self.detail()).status_code, 204)
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.archived_at)
        self.assertFalse(self.user.is_active)
        self.assertEqual(self.client.get(self.detail()).status_code, 404)
        self.assertEqual(self.client.get(BASE + "users").data["count"], 1)
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        self.assertEqual(self.client.get(BASE + "users/me").status_code, 401)
        self.assertEqual(self.register(username="reader").status_code, 400)

    def test_last_admin_cannot_be_disabled_demoted_or_archived(self):
        self.authorize(self.admin)
        for changes in ({"is_active": False}, {"role": "USER"}):
            self.assertEqual(
                self.client.patch(
                    self.detail(self.admin), changes, format="json"
                ).status_code,
                409,
            )
        self.assertEqual(
            self.client.delete(self.detail(self.admin)).status_code, 409
        )
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.role, "ADMIN")

    def test_admin_can_demote_when_another_active_admin_exists(self):
        self.user.role = "ADMIN"
        self.user.save()
        token = self.authorize(self.admin)
        self.assertEqual(
            self.client.patch(
                self.detail(self.admin),
                {
                    "role": "USER",
                },
                format="json",
            ).status_code,
            200,
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        self.assertEqual(self.client.get(BASE + "users").status_code, 403)

    def test_refresh_uses_current_role_and_rotates(self):
        token = self.authorize(self.admin)
        self.admin.role = "USER"
        self.admin.save()
        response = self.client.post(
            BASE + "auth/refresh", {"refresh": str(token)}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccessToken(response.data["access"])["role"], "USER")
        self.assertIn("refresh", response.data)
        self.assertEqual(
            self.client.post(
                BASE + "auth/refresh",
                {
                    "refresh": str(token),
                },
                format="json",
            ).status_code,
            401,
        )

    def test_password_change_revokes_old_access_and_refresh(self):
        token = self.authorize()
        self.authorize(self.admin)
        self.client.patch(
            self.detail(), {"password": "Changed!Password-2026"}, format="json"
        )
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        self.assertEqual(self.client.get(BASE + "users/me").status_code, 401)
        self.assertEqual(
            self.client.post(
                BASE + "auth/refresh",
                {
                    "refresh": str(token),
                },
                format="json",
            ).status_code,
            401,
        )

    def test_logout_blacklists_own_refresh(self):
        token = self.authorize()
        self.assertEqual(
            self.client.post(
                BASE + "auth/logout",
                {
                    "refresh": str(token),
                },
                format="json",
            ).status_code,
            204,
        )
        self.assertEqual(
            self.client.post(
                BASE + "auth/refresh",
                {
                    "refresh": str(token),
                },
                format="json",
            ).status_code,
            401,
        )

    def test_cannot_logout_another_users_refresh(self):
        other = LoginSerializer.get_token(self.admin)
        self.authorize()
        self.assertEqual(
            self.client.post(
                BASE + "auth/logout",
                {
                    "refresh": str(other),
                },
                format="json",
            ).status_code,
            400,
        )

    def test_invalid_and_expired_tokens(self):
        token = AccessToken.for_user(self.user)
        token.set_exp(lifetime=timedelta(seconds=-1))
        for access in ("invalid", str(token)):
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
            self.assertEqual(
                self.client.get(BASE + "users/me").status_code, 401
            )

    def test_invalid_refresh(self):
        self.assertEqual(
            self.client.post(
                BASE + "auth/refresh",
                {
                    "refresh": "invalid",
                },
                format="json",
            ).status_code,
            401,
        )

    def test_role_claim_alone_never_grants_admin_access(self):
        token = self.authorize()
        token["role"] = "ADMIN"
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {token.access_token}"
        )
        self.assertEqual(self.client.get(BASE + "users").status_code, 403)

    def test_wrong_signature_and_refresh_as_bearer_are_rejected(self):
        token = self.authorize()
        encoded = str(token.access_token)
        header, payload, signature = encoded.split(".")
        signature = ("A" if signature[0] != "A" else "B") + signature[1:]
        for value in (f"{header}.{payload}.{signature}", str(token)):
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {value}")
            self.assertEqual(
                self.client.get(BASE + "users/me").status_code, 401
            )

    def test_exact_username_query(self):
        self.authorize(self.admin)
        response = self.client.get(BASE + "users", {"username": "READER"})
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["username"], "reader")

    def test_fuzzy_username_query(self):
        self.authorize(self.admin)
        response = self.client.get(
            BASE + "users", {"username_contains": "READ"}
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["username"], "reader")

    def test_combined_role_and_active_filter(self):
        User.objects.create_user(
            "disabled_reader",
            "disabled@example.com",
            PASSWORD,
            is_active=False,
        )
        self.authorize(self.admin)
        response = self.client.get(
            BASE + "users",
            {
                "username_contains": "reader",
                "role": "USER",
                "is_active": "false",
            },
        )
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(
            response.data["results"][0]["username"], "disabled_reader"
        )

    def test_pagination(self):
        self.authorize(self.admin)
        one = self.client.get(
            BASE + "users", {"page_size": 1, "ordering": "username"}
        )
        two = self.client.get(
            BASE + "users", {"page_size": 1, "page": 2, "ordering": "username"}
        )
        self.assertEqual(one.data["count"], 2)
        self.assertEqual(two.data["page"], 2)
        self.assertNotEqual(
            one.data["results"][0]["id"], two.data["results"][0]["id"]
        )

    def test_invalid_queries(self):
        self.authorize(self.admin)
        for query in (
            {"role": "ROOT"},
            {"is_active": "1"},
            {"page": 0},
            {"page_size": 101},
            {"ordering": "password"},
            {"typo": "x"},
        ):
            self.assertEqual(
                self.client.get(BASE + "users", query).status_code, 400
            )
        self.assertEqual(
            self.client.get(BASE + "users?page=1&page=2").status_code, 400
        )
        self.assertEqual(
            self.client.get(BASE + "users?page=99").status_code, 404
        )

    def test_missing_or_invalid_user_id(self):
        self.authorize(self.admin)
        self.assertEqual(
            self.client.get(BASE + f"users/{uuid.uuid4()}").status_code, 404
        )
        response = self.client.get(BASE + "users/not-a-uuid")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["Content-Type"], "application/json")

    def test_bootstrap_superuser_role(self):
        admin = User.objects.create_superuser(
            "bootstrap", "bootstrap@example.com", PASSWORD
        )
        self.assertEqual(admin.role, "ADMIN")
        self.assertTrue(admin.check_password(PASSWORD))


class ConcurrentAdministratorTests(TransactionTestCase):
    def test_concurrent_self_demotions_leave_one_active_admin(self):
        AdministrationLock.objects.get_or_create(pk=1)
        admins = [
            User.objects.create_user(
                f"admin_{index}",
                f"admin{index}@example.com",
                PASSWORD,
                role="ADMIN",
            )
            for index in range(2)
        ]
        tokens = [
            str(LoginSerializer.get_token(user).access_token)
            for user in admins
        ]

        def demote(index):
            close_old_connections()
            try:
                client = APIClient()
                client.credentials(
                    HTTP_AUTHORIZATION=f"Bearer {tokens[index]}"
                )
                return client.patch(
                    BASE + f"users/{admins[index].pk}",
                    {
                        "role": "USER",
                    },
                    format="json",
                ).status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(demote, range(2)))
        self.assertEqual(sorted(results), [200, 409])
        self.assertEqual(
            User.objects.filter(role="ADMIN", is_active=True).count(), 1
        )
