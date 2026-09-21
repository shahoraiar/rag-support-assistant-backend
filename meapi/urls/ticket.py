from django.urls import path

from meapi.views.ticket import (
    TicketActivityListView,
    TicketAssignView,
    TicketCommentView,
    TicketDetailView,
    TicketListCreateView,
    TicketResolveView,
)

urlpatterns = [
    path("tickets/", TicketListCreateView.as_view(), name="ticket-list"),
    path("tickets/<str:ticket_uid>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("tickets/<str:ticket_uid>/comments/", TicketCommentView.as_view(), name="ticket-comment"),
    path("tickets/<str:ticket_uid>/assign/", TicketAssignView.as_view(), name="ticket-assign"),
    path("tickets/<str:ticket_uid>/resolve/", TicketResolveView.as_view(), name="ticket-resolve"),
    path("tickets/<str:ticket_uid>/activities/", TicketActivityListView.as_view(), name="ticket-activities"),
]
