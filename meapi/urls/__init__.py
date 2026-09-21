from django.urls import include, path

urlpatterns = [
    path("", include("meapi.urls.profile")),
    path("", include("meapi.urls.ticket")),
    path("", include("meapi.urls.chat")),
    path("", include("meapi.urls.knowledge")),
    path("", include("meapi.urls.notification")),
]
