from django.db import models


class UserRole(models.TextChoices):
    CUSTOMER = "customer", "Customer"
    AGENT = "agent", "Agent"
    ADMIN = "admin", "Admin"


class UserSource(models.TextChoices):
    EMAIL = "email", "Email / password"
    GOOGLE = "google", "Google"
