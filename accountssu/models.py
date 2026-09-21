from django.contrib.auth.models import AbstractUser
from django.db import models

from accountssu.choices import UserRole, UserSource


class User(AbstractUser):
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.CUSTOMER)
    source = models.CharField(
        max_length=20,
        choices=UserSource.choices,
        default=UserSource.EMAIL,
        help_text="How this account was created (email/password or Google).",
    )
    phone = models.CharField(max_length=20, blank=True)
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    max_open_tickets = models.PositiveIntegerField(default=10)
    is_available = models.BooleanField(default=True)

    class Meta:
        db_table = "users"

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.role})"

    @property
    def open_ticket_count(self):
        return self.assigned_tickets.filter(status__in=["open", "in_progress"]).count()
