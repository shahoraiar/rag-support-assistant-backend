import secrets

import requests
from django.conf import settings
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accountssu.choices import UserRole, UserSource
from accountssu.models import User
from globalapi.serializers.auth import (
    AuthResponseSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    PasswordResetConfirmResponseSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestResponseSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
)
from globalapi.utils.auth import (
    build_password_reset_url,
    get_user_from_reset_uid,
    is_valid_password_reset_token,
    send_password_reset_email,
    token_response,
    verify_google_id_token,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=RegisterSerializer,
        responses={201: AuthResponseSerializer},
        summary="Register a new account (role: agent or customer; default customer)",
    )
    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return token_response(user, status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=LoginSerializer,
        responses={
            200: AuthResponseSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        },
        summary="Login and get JWT tokens",
    )
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.check_password(password):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)
        return token_response(user)


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=GoogleLoginSerializer,
        responses={
            200: AuthResponseSerializer,
            201: AuthResponseSerializer,
            400: OpenApiResponse(description="Invalid Google credential"),
            503: OpenApiResponse(description="Google auth not configured"),
        },
        summary="Sign in / register with Google ID token",
    )
    def post(self, request):
        client_id = getattr(settings, "GOOGLE_CLIENT_ID", "") or ""
        if not client_id:
            return Response(
                {"detail": "Google sign-in is not configured on the server."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]

        try:
            idinfo = verify_google_id_token(credential, client_id)
        except (ValueError, requests.RequestException):
            return Response(
                {"detail": "Invalid Google credential."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email = (idinfo.get("email") or "").strip().lower()
        email_verified = str(idinfo.get("email_verified", "")).lower() in ("true", "1")
        if not email or not email_verified:
            return Response(
                {"detail": "Google account email is missing or not verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        name = (idinfo.get("name") or email.split("@")[0]).strip()

        user = User.objects.filter(email__iexact=email).first()
        created = False
        if user is None:
            user = User.objects.create_user(
                username=email,
                email=email,
                password=secrets.token_urlsafe(32),
                first_name=name,
                role=UserRole.CUSTOMER,
                source=UserSource.GOOGLE,
            )
            created = True
        else:
            if name and not user.first_name:
                user.first_name = name
                user.save(update_fields=["first_name"])

        return token_response(user, status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=PasswordResetRequestSerializer,
        responses={200: PasswordResetRequestResponseSerializer},
        summary="Request a password reset email",
    )
    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        # Always return the same message to avoid account enumeration.
        generic = {
            "detail": "If an account exists for this email, a password reset link has been sent.",
        }

        user = User.objects.filter(email__iexact=email).first()
        if user is None or not user.is_active:
            return Response(generic)

        reset_url = build_password_reset_url(user)
        try:
            send_password_reset_email(user, reset_url)
        except Exception as exc:
            if settings.DEBUG:
                return Response(
                    {"detail": f"Failed to send email: {exc}"},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
            return Response(
                {"detail": "Unable to send password reset email right now."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        if settings.DEBUG:
            generic["reset_url"] = reset_url
        return Response(generic)


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Auth"],
        request=PasswordResetConfirmSerializer,
        responses={
            200: PasswordResetConfirmResponseSerializer,
            400: OpenApiResponse(description="Invalid or expired reset link"),
        },
        summary="Confirm password reset with uid + token",
    )
    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uid = serializer.validated_data["uid"]
        token = serializer.validated_data["token"]
        password = serializer.validated_data["password"]

        user = get_user_from_reset_uid(uid)
        if user is None or not is_valid_password_reset_token(user, token):
            return Response(
                {"detail": "Invalid or expired reset link."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user.set_password(password)
        user.save(update_fields=["password"])

        return Response({"detail": "Password has been reset. You can sign in now."})
