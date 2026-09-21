import json
import re

from django.db import transaction
from django.db.models import Count, Q

from accountssu.models import User
from chatsu.choices import MessageRole
from chatsu.models import ChatMessage, ChatSession
from common.helpers import calculate_sla_due_at
from common.openrouter import chat_completion, chat_completion_or_none
from common.rag import retrieve_knowledge
from notificationssu.choices import NotificationType
from notificationssu.services import notify_agents_new_ticket, notify_ticket_assigned, notify_user
from ticketssu.choices import TicketActivityType, TicketCategory, TicketPriority, TicketSource, TicketStatus
from ticketssu.models import Ticket, TicketActivity, TicketMessage


AI_BOT_USERNAME = "supportai_bot"


def get_or_create_ai_bot_user() -> User:
    user, created = User.objects.get_or_create(
        username=AI_BOT_USERNAME,
        defaults={
            "email": "ai@supportai.local",
            "first_name": "SupportAI",
            "last_name": "Assistant",
            "role": "agent",
            "is_active": False,
            "is_available": False,
            "is_staff": False,
        },
    )
    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def _sender_for_chat_role(session: ChatSession, role: str, agent: User | None) -> User | None:
    if role == MessageRole.USER:
        return session.customer
    if role == MessageRole.AGENT:
        return agent or session.escalated_to_agent
    if role == MessageRole.ASSISTANT:
        return get_or_create_ai_bot_user()
    if role == MessageRole.SYSTEM:
        return get_or_create_ai_bot_user()
    return None


def sync_chat_history_to_ticket(session: ChatSession, ticket: Ticket) -> int:
    """Copy prior AI/human chat messages into the ticket conversation."""
    existing = {
        (sid, content)
        for sid, content in TicketMessage.objects.filter(ticket=ticket).values_list(
            "sender_id", "content"
        )
    }
    bot = get_or_create_ai_bot_user()
    created = 0
    for chat_msg in session.messages.order_by("created_at"):
        sender = _sender_for_chat_role(session, chat_msg.role, session.escalated_to_agent)
        if sender is None:
            continue
        content = chat_msg.content
        if chat_msg.role == MessageRole.ASSISTANT:
            content = f"[AI] {content}"
        elif chat_msg.role == MessageRole.SYSTEM:
            content = f"[System] {content}"

        key = (sender.id, content)
        if key in existing:
            continue

        ticket_msg = TicketMessage.objects.create(
            ticket=ticket,
            sender=sender or bot,
            content=content,
            is_internal=False,
        )
        TicketMessage.objects.filter(pk=ticket_msg.pk).update(
            created_at=chat_msg.created_at,
            updated_at=chat_msg.created_at,
        )
        existing.add(key)
        created += 1
    return created


def mirror_chat_message_to_ticket(chat_message: ChatMessage) -> TicketMessage | None:
    """Keep ticket conversation in sync after escalation."""
    session = chat_message.session
    ticket = session.ticket
    if ticket is None or session.is_ai_handled:
        return None
    if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        return None

    sender = _sender_for_chat_role(session, chat_message.role, session.escalated_to_agent)
    if sender is None:
        return None

    # Avoid duplicates if the same text was just posted on the ticket
    recent = (
        TicketMessage.objects.filter(ticket=ticket, sender=sender, content=chat_message.content)
        .order_by("-id")
        .first()
    )
    if recent and abs((recent.created_at - chat_message.created_at).total_seconds()) < 3:
        return recent

    ticket_msg = TicketMessage.objects.create(
        ticket=ticket,
        sender=sender,
        content=chat_message.content,
        is_internal=False,
    )
    from ticketssu.consumers import broadcast_ticket_event
    from meapi.serializers.ticket import TicketMessageSerializer

    broadcast_ticket_event(
        ticket.ticket_uid,
        "ticket.message",
        {"message": TicketMessageSerializer(ticket_msg).data},
    )
    return ticket_msg


def mirror_ticket_message_to_chat(ticket_message: TicketMessage) -> ChatMessage | None:
    """Keep live chat in sync when people reply on the ticket."""
    if ticket_message.is_internal:
        return None
    session = (
        ChatSession.objects.filter(ticket=ticket_message.ticket, is_ai_handled=False)
        .order_by("-id")
        .first()
    )
    if session is None:
        return None

    sender = ticket_message.sender
    if sender.role == "customer":
        role = MessageRole.USER
    elif sender.username == AI_BOT_USERNAME:
        role = MessageRole.ASSISTANT
    else:
        role = MessageRole.AGENT

    recent = (
        ChatMessage.objects.filter(session=session, role=role, content=ticket_message.content)
        .order_by("-id")
        .first()
    )
    if recent and abs((recent.created_at - ticket_message.created_at).total_seconds()) < 3:
        return recent

    chat_msg = ChatMessage.objects.create(
        session=session,
        role=role,
        content=ticket_message.content,
    )
    from chatsu.consumers import broadcast_chat_event
    from meapi.serializers.chat import ChatMessageSerializer

    broadcast_chat_event(
        session.id,
        "chat.message",
        {"message": ChatMessageSerializer(chat_msg).data},
    )
    return chat_msg

ESCALATION_KEYWORDS = (
    "talk to human",
    "human agent",
    "real person",
    "speak to someone",
    "talk to agent",
    "connect me to",
    "need an agent",
    "want a human",
    "manager",
    "supervisor",
    "এজেন্ট",
    "মানুষের সাথে",
    "মানুষ",
)

RAG_SYSTEM_PROMPT = (
    "You are SupportAI for an ISP help desk. "
    "Answer ONLY using the Knowledge base context provided in the user message. "
    "If the context contains the answer, state it clearly and confidently. "
    "Do not use outside knowledge. Do not invent policies, prices, or procedures. "
    "If the context does not answer the question, say you do not have that in the knowledge base "
    "and offer to connect the customer to a human agent. "
    "Keep answers concise."
)

REFUSAL_MESSAGE = (
    "I don't have that information in our knowledge base. "
    "I can only answer from our uploaded policy documents "
    "(billing/payments/refunds, terms of service, and privacy). "
    "Please rephrase using those topics, or say 'talk to a human agent'."
)

CLASSIFY_SYSTEM_PROMPT = (
    "You classify ISP customer support tickets using the knowledge-base context when provided. "
    "Reply with JSON only, no markdown. "
    'Format: {"priority":"low|medium|high|urgent","category":"billing|technical|account|general","sentiment":"positive|neutral|negative","reason":"short"} '
    "Priority guide: urgent = service down, fraud, security breach, double charge; "
    "high = payment/refund dispute, suspension, outage; "
    "medium = billing questions, installation, policy questions; "
    "low = general info, privacy policy questions with no urgency."
)

ESCALATION_SYSTEM_PROMPT = (
    "You decide if a customer support chat must be escalated to a human agent. "
    "Escalate when the customer explicitly wants a human, is very angry, has a billing dispute needing action, "
    "or the issue is too complex for self-service. "
    'Reply JSON only: {"escalate": true|false, "reason": "short reason"}'
)


def _parse_json_response(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return json.loads(cleaned)


def wants_human_agent(message: str) -> bool:
    lower = message.lower()
    return any(keyword in lower for keyword in ESCALATION_KEYWORDS)


def should_escalate(message: str, session: ChatSession) -> tuple[bool, str]:
    if wants_human_agent(message):
        return True, "Customer requested a human agent"

    lower = message.lower()
    frustration_signals = (
        "angry",
        "frustrated",
        "terrible",
        "worst",
        "unacceptable",
        "still not",
        "double charge",
        "charged twice",
        "not working",
        "doesn't work",
        "does not work",
    )
    if not any(signal in lower for signal in frustration_signals):
        return False, ""

    recent = list(session.messages.order_by("-created_at")[:6])
    history = "\n".join(f"{msg.role}: {msg.content}" for msg in reversed(recent))
    try:
        raw = chat_completion(
            [
                {
                    "role": "user",
                    "content": f"Conversation:\n{history}\n\nLatest message:\n{message}",
                }
            ],
            system_prompt=ESCALATION_SYSTEM_PROMPT,
        )
        data = _parse_json_response(raw)
        if data.get("escalate"):
            return True, data.get("reason", "Escalation recommended by AI")
    except Exception:
        return True, "Complex issue detected — escalating to human agent"

    return False, ""


def classify_ticket(conversation: str, *, subject: str = "") -> dict:
    """Classify priority/category via OpenRouter, grounded in knowledge-base snippets."""
    default = {
        "priority": TicketPriority.MEDIUM,
        "category": TicketCategory.GENERAL,
        "sentiment": "neutral",
    }
    text_blob = f"{subject}\n{conversation}".strip()
    lower = text_blob.lower()
    if any(word in lower for word in ("urgent", "double charge", "fraud", "hacked", "outage", "no internet", "down")):
        default["priority"] = TicketPriority.URGENT
    elif any(word in lower for word in ("refund", "suspension", "suspended", "reconnect", "error", "broken", "not working")):
        default["priority"] = TicketPriority.HIGH
    elif any(word in lower for word in ("privacy", "policy", "terms", "how do i", "question")):
        default["priority"] = TicketPriority.LOW

    if any(word in lower for word in ("bill", "charge", "payment", "refund", "invoice", "billing")):
        default["category"] = TicketCategory.BILLING
    elif any(word in lower for word in ("password", "login", "account", "privacy", "data", "terms")):
        default["category"] = TicketCategory.ACCOUNT
    elif any(word in lower for word in ("network", "outage", "installation", "activation", "wifi", "router", "technical")):
        default["category"] = TicketCategory.TECHNICAL

    from common.rag import retrieve_knowledge

    kb_query = f"{subject} {conversation}".strip()[:500]
    context, sources, _has_match = retrieve_knowledge(kb_query, limit=3)
    source_titles = [s.get("title", "") for s in sources if s.get("title")]

    user_prompt = (
        f"Subject: {subject or '(none)'}\n\n"
        f"Customer issue:\n{conversation[:2500]}\n\n"
        f"Knowledge base context:\n{context[:3500] if context else '(no matching chunks)'}\n\n"
        "Classify this ticket."
    )

    try:
        raw = chat_completion(
            [{"role": "user", "content": user_prompt}],
            system_prompt=CLASSIFY_SYSTEM_PROMPT,
        )
        data = _parse_json_response(raw)
        priority = data.get("priority", default["priority"])
        category = data.get("category", default["category"])
        if priority not in TicketPriority.values:
            priority = default["priority"]
        if category not in TicketCategory.values:
            category = default["category"]
        return {
            "priority": priority,
            "category": category,
            "sentiment": data.get("sentiment", default["sentiment"]),
            "reason": data.get("reason", ""),
            "sources": source_titles,
        }
    except Exception:
        return {**default, "reason": "fallback_rules", "sources": source_titles}


def pick_available_agent() -> User | None:
    """Assign only to agents who are online (is_available) — never offline agents."""
    agents = User.objects.filter(role="agent", is_active=True, is_available=True).annotate(
        open_count=Count(
            "assigned_tickets",
            filter=Q(assigned_tickets__status__in=[TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
        )
    )
    if not agents.exists():
        return None
    return min(agents, key=lambda agent: (agent.open_count, agent.id))


def build_conversation_text(session: ChatSession) -> str:
    return "\n".join(
        f"{message.role}: {message.content}"
        for message in session.messages.order_by("created_at")
    )


def generate_ai_reply(session: ChatSession, user_message: str) -> tuple[str, list[dict]]:
    context, sources, has_match = retrieve_knowledge(user_message)

    # Hard gate: no vector match → never invent an answer
    if not has_match or not context.strip():
        return REFUSAL_MESSAGE, []

    history = [
        {"role": "user" if msg.role == MessageRole.USER else "assistant", "content": msg.content}
        for msg in session.messages.order_by("-created_at")[:6]
        if msg.role in (MessageRole.USER, MessageRole.ASSISTANT)
    ][::-1]

    prompt = (
        "Knowledge base context (authoritative — answer only from this):\n"
        f"{context}\n\n"
        f"Customer question:\n{user_message}\n\n"
        "Reply using only the context above."
    )
    messages = history + [{"role": "user", "content": prompt}]
    answer = chat_completion_or_none(messages, system_prompt=RAG_SYSTEM_PROMPT)
    if answer:
        return answer, sources

    # Model unavailable: quote top chunk instead of inventing
    top = sources[0]
    return (
        f"From {top['title']}:\n{top['snippet']}\n\n"
        "If you need more help, say 'talk to a human agent'.",
        sources,
    )


@transaction.atomic
def escalate_chat_session(session: ChatSession, *, reason: str) -> tuple[Ticket, User | None]:
    if session.ticket_id:
        return session.ticket, session.escalated_to_agent

    conversation = build_conversation_text(session)
    first_user = session.messages.filter(role=MessageRole.USER).order_by("created_at").first()
    subject = (first_user.content[:120] if first_user else "Chat escalation").replace("\n", " ")
    classification = classify_ticket(conversation, subject=subject)
    priority = classification["priority"]

    agent = pick_available_agent()
    ticket = Ticket.objects.create(
        customer=session.customer,
        subject=subject,
        description=conversation,
        priority=priority,
        category=classification["category"],
        source=TicketSource.CHAT,
        status=TicketStatus.IN_PROGRESS if agent else TicketStatus.OPEN,
        ai_classification=classification,
        sla_due_at=calculate_sla_due_at(priority),
    )
    if agent:
        ticket.assigned_agent = agent
        ticket.save(update_fields=["assigned_agent", "updated_at"])

    session.is_ai_handled = False
    session.escalated_to_agent = agent
    session.ticket = ticket
    session.save(update_fields=["is_ai_handled", "escalated_to_agent", "ticket", "updated_at"])

    TicketActivity.objects.create(
        ticket=ticket,
        activity_type=TicketActivityType.CREATED,
        message="Ticket created from AI chat escalation",
        actor=session.customer,
    )
    TicketActivity.objects.create(
        ticket=ticket,
        activity_type=TicketActivityType.AI_CLASSIFIED,
        message=(
            f"AI classified as {classification['category'].title()} · "
            f"{classification['priority'].title()} priority"
        ),
    )
    if agent:
        TicketActivity.objects.create(
            ticket=ticket,
            activity_type=TicketActivityType.AGENT_ASSIGNED,
            message=f"{agent.get_full_name()} assigned automatically",
            actor=agent,
        )
        notify_ticket_assigned(ticket=ticket, agent=agent)
        notify_user(
            user=agent,
            notification_type=NotificationType.CHAT_ESCALATED,
            title="Chat escalated to you",
            message=f"Customer {session.customer.get_full_name()} needs help: {subject}",
            metadata={
                "ticket_uid": ticket.ticket_uid,
                "session_id": session.id,
                "chat_uid": session.chat_uid,
                "reason": reason,
            },
        )
    else:
        notify_agents_new_ticket(ticket=ticket)
    TicketActivity.objects.create(
        ticket=ticket,
        activity_type=TicketActivityType.CHAT_ESCALATED,
        message=reason,
        actor=session.customer,
    )
    notify_user(
        user=session.customer,
        notification_type=NotificationType.CHAT_ESCALATED,
        title="Connected to support",
        message=(
            f"You are now connected with {agent.get_full_name()}"
            if agent
            else "Your request was escalated. An agent will join shortly."
        ),
        metadata={
            "ticket_uid": ticket.ticket_uid,
            "session_id": session.id,
            "chat_uid": session.chat_uid,
        },
    )

    ChatMessage.objects.create(
        session=session,
        role=MessageRole.SYSTEM,
        content=(
            f"Connected to {agent.get_full_name()}. Ticket {ticket.ticket_uid} created. "
            f"AI chat is closed — open My Tickets and select {ticket.ticket_uid} to continue."
            if agent
            else (
                f"Ticket {ticket.ticket_uid} created. AI chat is closed — "
                f"open My Tickets and select {ticket.ticket_uid} to continue with an agent."
            )
        ),
    )
    # Copy AI + chat history (including the system note) onto the ticket thread
    sync_chat_history_to_ticket(session, ticket)

    from meapi.serializers.ticket import TicketSerializer
    from ticketssu.consumers import broadcast_agent_queue_event

    broadcast_agent_queue_event(
        "ticket.created",
        {"ticket": TicketSerializer(ticket).data},
    )
    return ticket, agent
