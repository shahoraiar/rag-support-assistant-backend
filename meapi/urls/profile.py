from django.urls import path

from meapi.views.profile import (
    AgentAvailabilityView,
    AgentListView,
    AgentSetPasswordView,
    AgentWorkloadView,
    CustomerListView,
    MeView,
)

urlpatterns = [
    path("auth/me/", MeView.as_view(), name="me"),
    path("agents/", AgentListView.as_view(), name="agent-list"),
    path("agents/workload/", AgentWorkloadView.as_view(), name="agent-workload"),
    path("agents/me/availability/", AgentAvailabilityView.as_view(), name="agent-availability"),
    path(
        "agents/<int:pk>/set-password/",
        AgentSetPasswordView.as_view(),
        name="agent-set-password",
    ),
    path("customers/", CustomerListView.as_view(), name="customer-list"),
]
