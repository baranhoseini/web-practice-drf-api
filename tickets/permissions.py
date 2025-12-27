from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.permissions import is_support

class TicketObjectPermission(BasePermission):
    """
    - Owner can read/update their ticket
    - Support/Admin can read/update/delete any ticket
    - Non-owner cannot update/delete others
    """
    def has_object_permission(self, request, view, obj):
        if is_support(request.user):
            return True
        if request.method in SAFE_METHODS:
            return obj.creator_id == request.user.id
        return obj.creator_id == request.user.id

    def has_permission(self, request, view):
        # any authenticated user can access endpoints, object rules handled above
        return bool(request.user and request.user.is_authenticated)
