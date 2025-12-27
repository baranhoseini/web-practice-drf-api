from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.permissions import is_support

class IsAdOwnerOrSupportAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        return obj.creator_id == request.user.id or is_support(request.user)
