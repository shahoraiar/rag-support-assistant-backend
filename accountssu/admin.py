from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accountssu.models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "source", "is_available", "is_active", "date_joined")
    list_filter = ("role", "source", "is_available", "is_active")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("SupportAI", {"fields": ("role", "source", "phone", "avatar", "max_open_tickets", "is_available")}),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        ("SupportAI", {"fields": ("role", "source", "phone")}),
    )
    readonly_fields = ("source",)
