from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.views import APIView

from chatsu.choices import MessageRole
from chatsu.consumers import broadcast_chat_event
from chatsu.models import ChatMessage, ChatSession
from chatsu.services import escalate_chat_session, generate_ai_reply, should_escalate
from common.permissions import IsCustomer
from meapi.serializers.chat import ChatMessageCreateSerializer, ChatMessageSerializer, ChatSessionSerializer


def _push_message(session_id: int, message: ChatMessage) -> None:
    broadcast_chat_event(
        session_id,
        "chat.message",
        {"message": ChatMessageSerializer(message).data},
    )


class ChatSessionListCreateView(generics.ListCreateAPIView):
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ChatSession.objects.prefetch_related("messages").select_related(
            "customer", "ticket", "escalated_to_agent"
        )
        if user.role == "customer":
            return qs.filter(customer=user)
        if user.role == "agent":
            # All live/escalated chats — not only ones assigned to this agent
            return qs.filter(is_ai_handled=False)
        return qs

    def perform_create(self, serializer):
        session = serializer.save(customer=self.request.user)
        ChatMessage.objects.create(
            session=session,
            role=MessageRole.ASSISTANT,
            content="Hi! I'm SupportAI. Ask me about billing, refunds, or your account. I can connect you to a human agent anytime.",
        )


class ChatSessionDetailView(generics.RetrieveAPIView):
    serializer_class = ChatSessionSerializer

    def get_queryset(self):
        user = self.request.user
        qs = ChatSession.objects.prefetch_related("messages").select_related(
            "customer", "ticket", "escalated_to_agent"
        )
        if user.role == "customer":
            return qs.filter(customer=user)
        if user.role == "agent":
            return qs.filter(is_ai_handled=False)
        return qs


class ChatMessageView(APIView):
    def post(self, request, pk):
        try:
            session = ChatSession.objects.prefetch_related("messages").get(pk=pk)
        except ChatSession.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if request.user.role == "customer" and session.customer_id != request.user.id:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role == "customer" and not session.is_ai_handled:
            ticket_uid = session.ticket.ticket_uid if session.ticket_id else None
            return Response(
                {
                    "detail": (
                        f"AI chat is closed. Open My Tickets"
                        + (f" and select {ticket_uid}" if ticket_uid else "")
                        + " to continue the conversation."
                    ),
                    "ticket_id": ticket_uid,
                    "escalated": True,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if request.user.role == "agent" and session.is_ai_handled:
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        if request.user.role == "agent" and session.escalated_to_agent_id is None:
            session.escalated_to_agent = request.user
            session.save(update_fields=["escalated_to_agent", "updated_at"])

        serializer = ChatMessageCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        content = serializer.validated_data["content"]

        user_msg = ChatMessage.objects.create(
            session=session,
            role=MessageRole.USER if request.user.role == "customer" else MessageRole.AGENT,
            content=content,
        )

        if not session.is_ai_handled:
            from chatsu.services import mirror_chat_message_to_ticket
            from notificationssu.services import notify_ticket_reply

            mirror_chat_message_to_ticket(user_msg)
            if session.ticket_id:
                notify_ticket_reply(
                    ticket=session.ticket,
                    sender=request.user,
                    content=content,
                    is_internal=False,
                )
            _push_message(session.id, user_msg)
            return Response(
                {
                    "user_message": ChatMessageSerializer(user_msg).data,
                    "escalated": True,
                    "ticket_id": session.ticket.ticket_uid if session.ticket else None,
                },
                status=status.HTTP_201_CREATED,
            )

        escalate, reason = should_escalate(content, session)
        if escalate:
            ticket, agent = escalate_chat_session(session, reason=reason)
            system_msg = session.messages.filter(role=MessageRole.SYSTEM).order_by("-created_at").first()
            _push_message(session.id, user_msg)
            if system_msg:
                _push_message(session.id, system_msg)
            return Response(
                {
                    "user_message": ChatMessageSerializer(user_msg).data,
                    "escalated": True,
                    "ticket_id": ticket.ticket_uid,
                    "agent_name": agent.get_full_name() if agent else None,
                    "system_message": ChatMessageSerializer(system_msg).data if system_msg else None,
                },
                status=status.HTTP_201_CREATED,
            )

        try:
            answer, sources = generate_ai_reply(session, content)
        except Exception:
            return Response(
                {"detail": "Could not generate AI response. Please try again or use Talk to human."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        ai_msg = ChatMessage.objects.create(
            session=session,
            role=MessageRole.ASSISTANT,
            content=answer,
            sources=sources,
        )
        return Response(
            {
                "user_message": ChatMessageSerializer(user_msg).data,
                "ai_message": ChatMessageSerializer(ai_msg).data,
                "escalated": False,
            },
            status=status.HTTP_201_CREATED,
        )


class ChatEscalateView(APIView):
    permission_classes = [IsCustomer]

    def post(self, request, pk):
        try:
            session = ChatSession.objects.get(pk=pk, customer=request.user)
        except ChatSession.DoesNotExist:
            return Response({"detail": "Not found"}, status=status.HTTP_404_NOT_FOUND)

        if not session.is_ai_handled:
            return Response(
                {
                    "detail": "Chat already escalated",
                    "ticket_id": session.ticket.ticket_uid if session.ticket else None,
                    "agent_name": session.escalated_to_agent.get_full_name() if session.escalated_to_agent else None,
                },
                status=status.HTTP_200_OK,
            )

        ticket, agent = escalate_chat_session(session, reason="Customer requested human support")
        system_msg = session.messages.filter(role=MessageRole.SYSTEM).order_by("-created_at").first()
        if system_msg:
            _push_message(session.id, system_msg)
        return Response(
            {
                "escalated": True,
                "ticket_id": ticket.ticket_uid,
                "agent_name": agent.get_full_name() if agent else None,
                "system_message": ChatMessageSerializer(system_msg).data if system_msg else None,
            },
            status=status.HTTP_200_OK,
        )


class ChatAskView(APIView):
    def post(self, request):
        question = request.data.get("question", "").strip()
        if not question:
            return Response({"detail": "question is required"}, status=status.HTTP_400_BAD_REQUEST)

        from chatsu.services import REFUSAL_MESSAGE, RAG_SYSTEM_PROMPT
        from common.rag import retrieve_knowledge
        from common.openrouter import chat_completion_or_none

        context, sources, has_match = retrieve_knowledge(question)
        if not has_match or not context.strip():
            return Response({"answer": REFUSAL_MESSAGE, "sources": []})

        answer = chat_completion_or_none(
            [
                {
                    "role": "user",
                    "content": (
                        "Knowledge base context (authoritative — answer only from this):\n"
                        f"{context}\n\nQuestion:\n{question}\n\n"
                        "Reply using only the context above."
                    ),
                }
            ],
            system_prompt=RAG_SYSTEM_PROMPT,
        )
        if not answer:
            top = sources[0]
            answer = (
                f"From {top['title']}:\n{top['snippet']}\n\n"
                "If you need more help, say 'talk to a human agent'."
            )

        return Response({"answer": answer, "sources": sources})
