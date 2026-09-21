import requests
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from accountssu.models import User
from meapi.serializers.profile import UserSerializer

password_reset_token_generator = PasswordResetTokenGenerator()


def token_response(user, http_status=status.HTTP_200_OK):
    """Build a standard JWT auth response payload."""
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        },
        status=http_status,
    )


def verify_google_id_token(credential: str, client_id: str) -> dict:
    """Verify Google ID token via Google's tokeninfo endpoint."""
    response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"id_token": credential},
        timeout=10,
    )
    if response.status_code != 200:
        raise ValueError("Invalid Google credential")

    payload = response.json()
    aud = payload.get("aud")
    if aud != client_id:
        raise ValueError("Google credential audience mismatch")
    return payload


def build_password_reset_url(user) -> str:
    # Encode user pk so the frontend can send it back safely in the confirm request
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    # One-time token tied to this user's current password hash (invalid after reset / change)
    token = password_reset_token_generator.make_token(user)
    # FRONTEND_URL from .env — email link opens the React reset page, not the API
    base = getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")
    return f"{base}/reset-password?uid={uid}&token={token}"


def send_password_reset_email(user, reset_url: str) -> None:
    """Send password-reset email (text + branded HTML) via configured EMAIL_BACKEND."""
    from django.template.loader import render_to_string

    name = user.get_full_name() or user.email
    subject = "Reset your SupportAI password"
    context = {"name": name, "reset_url": reset_url}
    text_body = (
        f"Hi {name},\n\n"
        "We received a request to reset your SupportAI password.\n"
        "Open this link to choose a new password:\n\n"
        f"{reset_url}\n\n"
        "If you did not request this, you can ignore this email.\n"
        "Your password will stay the same.\n\n"
        "— SupportAI\n"
    )
    html_body = render_to_string("emails/password_reset.html", context)
    message = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html_body, "text/html")
    message.send(fail_silently=False)


def get_user_from_reset_uid(uid: str) -> User | None:
    """Decode password-reset uid and return the user, or None if invalid."""
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        return User.objects.get(pk=user_id)
    except (User.DoesNotExist, ValueError, TypeError, OverflowError):
        return None


def is_valid_password_reset_token(user, token: str) -> bool:
    return password_reset_token_generator.check_token(user, token)
