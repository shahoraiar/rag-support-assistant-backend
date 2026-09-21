from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from globalapi.views.auth import (
    GoogleLoginView,
    LoginView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegisterView,
)

urlpatterns = [
    path("auth/register/", RegisterView.as_view(), name="auth-register"),
    path("auth/login/", LoginView.as_view(), name="auth-login"),
    path("auth/google/", GoogleLoginView.as_view(), name="auth-google"),
    path("auth/password-reset/", PasswordResetRequestView.as_view(), name="auth-password-reset"),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="auth-password-reset-confirm",
    ),
    path("auth/refresh/", TokenRefreshView.as_view(), name="auth-refresh"),
]
