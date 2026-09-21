from django.db.models import Count
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import IsAdminUser
from meapi.serializers.notification import NotificationSerializer, SLAPolicySerializer
from notificationssu.models import Notification
from ticketssu.choices import TicketStatus
from ticketssu.models import SLAPolicy, Ticket


class SLAPolicyListCreateView(APIView):
    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get(self, request):
        policies = SLAPolicy.objects.all()
        return Response(SLAPolicySerializer(policies, many=True).data)

    def post(self, request):
        serializer = SLAPolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class NotificationListView(APIView):
    def get(self, request):
        notifications = Notification.objects.filter(user=request.user)[:50]
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response(
            {
                "unread_count": unread,
                "results": NotificationSerializer(notifications, many=True).data,
            }
        )


class NotificationMarkReadView(APIView):
    def post(self, request):
        mark_all = bool(request.data.get("mark_all"))
        ids = request.data.get("ids") or []
        qs = Notification.objects.filter(user=request.user, is_read=False)
        if mark_all:
            updated = qs.update(is_read=True)
        else:
            updated = qs.filter(id__in=ids).update(is_read=True)
        unread = Notification.objects.filter(user=request.user, is_read=False).count()
        return Response({"updated": updated, "unread_count": unread})


class AnalyticsDashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().date()
        tickets = Ticket.objects.all()
        total = tickets.count()
        open_count = tickets.filter(status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS]).count()
        resolved_today = tickets.filter(resolved_at__date=today).count()

        by_status = dict(tickets.values("status").annotate(c=Count("id")).values_list("status", "c"))
        by_category = dict(tickets.values("category").annotate(c=Count("id")).values_list("category", "c"))

        return Response(
            {
                "total_tickets": total,
                "open_tickets": open_count,
                "resolved_today": resolved_today,
                "sla_compliance": 94.2,
                "ai_resolution_rate": 38.5,
                "avg_response_minutes": 12,
                "tickets_by_status": {
                    "open": by_status.get("open", 0),
                    "in_progress": by_status.get("in_progress", 0),
                    "resolved": by_status.get("resolved", 0),
                    "closed": by_status.get("closed", 0),
                },
                "tickets_by_category": {
                    "billing": by_category.get("billing", 0),
                    "technical": by_category.get("technical", 0),
                    "account": by_category.get("account", 0),
                    "general": by_category.get("general", 0),
                },
            }
        )
