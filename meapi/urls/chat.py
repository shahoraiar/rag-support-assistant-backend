from django.urls import path

from meapi.views.chat import (
    ChatAskView,
    ChatEscalateView,
    ChatMessageView,
    ChatSessionDetailView,
    ChatSessionListCreateView,
)

urlpatterns = [
    path("chat/sessions/", ChatSessionListCreateView.as_view(), name="chat-sessions"),
    path("chat/sessions/<int:pk>/", ChatSessionDetailView.as_view(), name="chat-session-detail"),
    path("chat/sessions/<int:pk>/messages/", ChatMessageView.as_view(), name="chat-messages"),
    path("chat/sessions/<int:pk>/escalate/", ChatEscalateView.as_view(), name="chat-escalate"),
    path("chat/ask/", ChatAskView.as_view(), name="chat-ask"),
]
