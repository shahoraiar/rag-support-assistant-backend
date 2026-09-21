from django.contrib import admin

from chatsu.models import ChatMessage, ChatSession


class ChatMessageInline(admin.TabularInline):
    model = ChatMessage
    extra = 0


@admin.register(ChatSession)
class ChatSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "customer", "is_ai_handled", "escalated_to_agent", "created_at")
    inlines = [ChatMessageInline]
