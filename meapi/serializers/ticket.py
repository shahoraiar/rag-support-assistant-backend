from rest_framework import serializers

from ticketssu.models import Ticket, TicketActivity, TicketMessage


class TicketMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.CharField(source="sender.get_full_name", read_only=True)
    sender_id = serializers.IntegerField(source="sender.id", read_only=True)

    class Meta:
        model = TicketMessage
        fields = ("id", "ticket", "sender_id", "sender_name", "content", "is_internal", "seen_at", "created_at")
        read_only_fields = ("id", "sender_id", "sender_name", "created_at")


class TicketActivitySerializer(serializers.ModelSerializer):
    actor_name = serializers.CharField(source="actor.get_full_name", read_only=True, allow_null=True)

    class Meta:
        model = TicketActivity
        fields = ("id", "ticket", "activity_type", "message", "actor_name", "created_at")


class TicketSerializer(serializers.ModelSerializer):
    customer_id = serializers.IntegerField(source="customer.id", read_only=True)
    customer_name = serializers.CharField(source="customer.get_full_name", read_only=True)
    assigned_agent_id = serializers.IntegerField(source="assigned_agent.id", read_only=True, allow_null=True)
    assigned_agent_name = serializers.CharField(source="assigned_agent.get_full_name", read_only=True, allow_null=True)
    id = serializers.CharField(source="ticket_uid", read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id", "subject", "description", "status", "priority", "category", "source",
            "customer_id", "customer_name", "assigned_agent_id", "assigned_agent_name",
            "sla_due_at", "first_response_at", "resolved_at", "ai_classification",
            "created_at", "updated_at",
        )
        read_only_fields = (
            "id", "status", "priority", "category", "customer_id", "customer_name",
            "assigned_agent_id", "assigned_agent_name", "sla_due_at", "ai_classification",
            "created_at", "updated_at",
        )


class TicketCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ticket
        fields = ("subject", "description")

    def create(self, validated_data):
        user = self.context["request"].user
        from chatsu.services import classify_ticket
        from common.helpers import calculate_sla_due_at
        from ticketssu.choices import TicketActivityType, TicketSource
        from ticketssu.models import TicketActivity, TicketMessage

        subject = validated_data["subject"]
        description = validated_data["description"]
        classification = classify_ticket(description, subject=subject)
        priority = classification["priority"]
        category = classification["category"]

        ticket = Ticket.objects.create(
            customer=user,
            subject=subject,
            description=description,
            priority=priority,
            category=category,
            source=TicketSource.WEB,
            ai_classification=classification,
            sla_due_at=calculate_sla_due_at(priority),
        )
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type=TicketActivityType.CREATED,
            message="Ticket submitted successfully",
            actor=user,
        )
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type=TicketActivityType.AI_CLASSIFIED,
            message=(
                f"AI classified as {priority} priority / {category}"
                + (f" — {classification.get('reason')}" if classification.get("reason") else "")
            ),
        )

        TicketMessage.objects.create(
            ticket=ticket,
            sender=user,
            content=ticket.description,
            is_internal=False,
        )
        from meapi.serializers.ticket import TicketSerializer
        from notificationssu.services import notify_agents_new_ticket
        from ticketssu.consumers import broadcast_agent_queue_event

        broadcast_agent_queue_event(
            "ticket.created",
            {"ticket": TicketSerializer(ticket).data},
        )
        notify_agents_new_ticket(ticket=ticket)
        return ticket
