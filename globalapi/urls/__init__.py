from django.urls import include, path

urlpatterns = [
    path("", include("globalapi.urls.auth")),
]
