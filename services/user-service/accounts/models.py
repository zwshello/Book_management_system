import uuid

from django.contrib.auth.models import (
    AbstractUser,
    UserManager as DjangoUserManager,
)
from django.db import models


class UserManager(DjangoUserManager):
    @classmethod
    def normalize_email(cls, email):
        return (email or "").strip().casefold()

    def create_user(self, username, email=None, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        username = self.model.normalize_username(username)
        return super().create_user(username, email, password, **extra_fields)

    def create_superuser(
        self, username, email=None, password=None, **extra_fields
    ):
        extra_fields.setdefault("role", User.Role.ADMIN)
        if extra_fields["role"] != User.Role.ADMIN:
            raise ValueError("Superuser must have ADMIN role")
        return super().create_superuser(
            username, email, password, **extra_fields
        )


class User(AbstractUser):
    class Role(models.TextChoices):
        USER = "USER", "普通用户"
        ADMIN = "ADMIN", "管理员"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    display_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(
        max_length=5, choices=Role.choices, default=Role.USER
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    objects = UserManager()
    REQUIRED_FIELDS = ["email"]

    @classmethod
    def normalize_username(cls, username):
        return super().normalize_username(username).strip().casefold()

    def save(self, *args, **kwargs):
        self.username = self.normalize_username(self.username)
        self.email = UserManager.normalize_email(self.email)
        super().save(*args, **kwargs)

    class Meta:
        db_table = "users"
        ordering = ["-created_at", "id"]
        indexes = [models.Index(fields=["role", "is_active", "archived_at"])]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(role__in=["USER", "ADMIN"]),
                name="users_valid_role",
            ),
        ]


class AdministrationLock(models.Model):
    """One row serializes admin mutations to protect the last active admin."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)

    class Meta:
        db_table = "user_administration_lock"
