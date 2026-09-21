import os

from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import OriginValidator
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "supportai.settings")

django_asgi_app = get_asgi_application()

from chatsu.middleware import JwtAuthMiddlewareStack  # noqa: E402
from chatsu.routing import websocket_urlpatterns  # noqa: E402

# Cross-origin WS (Vercel frontend → DuckDNS API) needs Origin allowlist,
# not AllowedHostsOriginValidator (that only matches ALLOWED_HOSTS / API host).
_ws_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if o.strip()
]

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": OriginValidator(
            JwtAuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
            _ws_origins,
        ),
    }
)
