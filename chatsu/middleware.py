from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken


@database_sync_to_async
def _user_from_token(token: str):
    from accountssu.models import User

    try:
        access = AccessToken(token)
        return User.objects.get(pk=access["user_id"])
    except Exception:
        return AnonymousUser()


class JwtAuthMiddleware(BaseMiddleware):
    """Authenticate WebSocket connections via ?token=<jwt> query param."""

    async def __call__(self, scope, receive, send):
        query = parse_qs(scope.get("query_string", b"").decode())
        raw = (query.get("token") or [None])[0]
        scope["user"] = await _user_from_token(raw) if raw else AnonymousUser()
        return await super().__call__(scope, receive, send)


def JwtAuthMiddlewareStack(inner):
    return JwtAuthMiddleware(inner)
