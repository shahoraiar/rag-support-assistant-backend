from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accountssu.models import User
from common.permissions import IsAdminUser, IsAgentOrAdmin
from meapi.serializers.admin_user import AdminSetPasswordSerializer
from meapi.serializers.profile import AgentProfileSerializer, UserSerializer


class MeView(APIView):
    @extend_schema(tags=["Profile"], responses=UserSerializer, summary="Get current user profile")
    def get(self, request):
        return Response(UserSerializer(request.user).data)


class AgentListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAgentOrAdmin]

    def get_queryset(self):
        return User.objects.filter(role="agent").order_by("first_name", "last_name", "id")


class CustomerListView(generics.ListAPIView):
    serializer_class = UserSerializer
    permission_classes = [IsAdminUser]

    def get_queryset(self):
        return User.objects.filter(role="customer").order_by("-date_joined", "id")


class AgentSetPasswordView(APIView):
    permission_classes = [IsAdminUser]

    @extend_schema(
        tags=["Profile"],
        request=AdminSetPasswordSerializer,
        responses={200: UserSerializer},
        summary="Admin sets a new password for an agent",
    )
    def post(self, request, pk):
        try:
            agent = User.objects.get(pk=pk, role="agent")
        except User.DoesNotExist:
            return Response({"detail": "Agent not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = AdminSetPasswordSerializer(
            data=request.data,
            context={"user": agent},
        )
        serializer.is_valid(raise_exception=True)
        agent.set_password(serializer.validated_data["password"])
        agent.save(update_fields=["password"])
        return Response(
            {
                "detail": f"Password updated for {agent.get_full_name() or agent.email}.",
                "user": UserSerializer(agent).data,
            }
        )


class AgentWorkloadView(APIView):
    permission_classes = [IsAgentOrAdmin]

    def get(self, request):
        agents = User.objects.filter(role="agent")
        data = [
            {
                "agent_id": agent.id,
                "agent_name": agent.get_full_name(),
                "open_tickets": agent.open_ticket_count,
                "max_tickets": agent.max_open_tickets,
                "is_available": agent.is_available,
            }
            for agent in agents
        ]
        return Response(data)


class AgentAvailabilityView(APIView):
    permission_classes = [IsAgentOrAdmin]

    def patch(self, request):
        user = request.user
        if user.role != "agent":
            return Response({"detail": "Only agents can toggle availability."}, status=status.HTTP_403_FORBIDDEN)
        is_available = request.data.get("is_available")
        if is_available is not None:
            user.is_available = bool(is_available)
            user.save(update_fields=["is_available"])
        return Response(AgentProfileSerializer(user).data)
