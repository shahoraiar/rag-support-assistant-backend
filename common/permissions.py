from rest_framework.permissions import BasePermission


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "customer"


class IsAgent(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "agent"


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == "admin"


class IsAgentOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ("agent", "admin")
