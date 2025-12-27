from rest_framework.permissions import BasePermission, SAFE_METHODS
from accounts.permissions import is_support

class IsReviewAuthorOrSupport(BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_support(request.user):
            return True
        if request.method in SAFE_METHODS:
            return True
        return obj.author_id == request.user.id
