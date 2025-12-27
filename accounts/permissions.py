from rest_framework.permissions import BasePermission

def is_admin(user):
    return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, "role", None) == "ADMIN"))

def is_support(user):
    return bool(user and user.is_authenticated and (is_admin(user) or getattr(user, "role", None) == "SUPPORT"))

def is_customer(user):
    return bool(user and user.is_authenticated and getattr(user, "role", None) == "CUSTOMER")

def is_contractor(user):
    return bool(user and user.is_authenticated and getattr(user, "role", None) == "CONTRACTOR")


class IsSupportOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_support(request.user)


class IsCustomer(BasePermission):
    def has_permission(self, request, view):
        return is_customer(request.user)


class IsContractor(BasePermission):
    def has_permission(self, request, view):
        return is_contractor(request.user)
