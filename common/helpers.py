from django.utils import timezone


def calculate_sla_due_at(priority: str):
    from ticketssu.models import SLAPolicy

    policy = SLAPolicy.objects.filter(priority=priority, is_active=True).first()
    hours = policy.first_response_hours if policy else 24
    return timezone.now() + timezone.timedelta(hours=hours)
