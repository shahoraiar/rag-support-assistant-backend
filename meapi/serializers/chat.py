from rest_framework import serializers

from chatsu.models import ChatMessage, ChatSession


class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ("id", "role", "content", "sources", "seen_at", "created_at")


class ChatSessionSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    ticket_id = serializers.CharField(source="ticket.ticket_uid", read_only=True, allow_null=True)
    escalated_to_agent_name = serializers.SerializerMethodField()
    messages = ChatMessageSerializer(many=True, read_only=True)

    class Meta:
        model = ChatSession
        fields = (
            "id",
            "chat_uid",
            "customer_id",
            "customer_name",
            "ticket_id",
            "is_ai_handled",
            "escalated_to_agent",
            "escalated_to_agent_name",
            "messages",
            "created_at",
        )

    def get_escalated_to_agent_name(self, obj):
        if obj.escalated_to_agent:
            return obj.escalated_to_agent.get_full_name()
        return None


class ChatMessageCreateSerializer(serializers.Serializer):
    content = serializers.CharField()
