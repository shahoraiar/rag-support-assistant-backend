from rest_framework import serializers

from accountssu.models import User


class UserSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "name", "email", "role", "source", "phone", "avatar", "is_available")

    def get_name(self, obj):
        return obj.get_full_name() or obj.username


class AgentProfileSerializer(serializers.ModelSerializer):
    agent_name = serializers.CharField(source="get_full_name", read_only=True)
    open_tickets = serializers.IntegerField(source="open_ticket_count", read_only=True)

    class Meta:
        model = User
        fields = ("id", "agent_name", "max_open_tickets", "is_available", "open_tickets")
