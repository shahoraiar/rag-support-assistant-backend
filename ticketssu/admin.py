from django.contrib import admin

from ticketssu.models import SLAPolicy, Ticket, TicketActivity, TicketMessage


class TicketMessageInline(admin.TabularInline):
    model = TicketMessage
    extra = 0


class TicketActivityInline(admin.TabularInline):
    model = TicketActivity
    extra = 0


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ("ticket_uid", "subject", "customer", "status", "priority", "assigned_agent", "created_at")
    list_filter = ("status", "priority", "category")
    search_fields = ("ticket_uid", "subject")
    inlines = [TicketMessageInline, TicketActivityInline]


@admin.register(SLAPolicy)
class SLAPolicyAdmin(admin.ModelAdmin):
    list_display = ("priority", "first_response_hours", "resolution_hours", "is_active")
