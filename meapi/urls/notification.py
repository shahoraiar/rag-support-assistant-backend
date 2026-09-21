from django.urls import path

from meapi.views.analytics import (
    AnalyticsDashboardView,
    NotificationListView,
    NotificationMarkReadView,
    SLAPolicyListCreateView,
)

urlpatterns = [
    path("sla/", SLAPolicyListCreateView.as_view(), name="sla-policies"),
    path("notifications/", NotificationListView.as_view(), name="notifications"),
    path("notifications/mark-read/", NotificationMarkReadView.as_view(), name="notifications-mark-read"),
    path("analytics/dashboard/", AnalyticsDashboardView.as_view(), name="analytics-dashboard"),
]
