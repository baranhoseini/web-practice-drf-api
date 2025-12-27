from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import User
from .models import Ticket
from .serializers import TicketSerializer


class TicketViewSet(viewsets.ModelViewSet):
    serializer_class = TicketSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        u = self.request.user
        if u.role in (User.Role.SUPPORT, User.Role.ADMIN):
            return Ticket.objects.all().order_by("-created_at")
        return Ticket.objects.filter(creator=u).order_by("-created_at")

    def perform_create(self, serializer):
        serializer.save(creator=self.request.user)

    def update(self, request, *args, **kwargs):
        """
        Full update (PUT). We enforce the same logic as partial update.
        """
        return self._safe_update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """
        Partial update (PATCH).
        """
        return self._safe_update(request, *args, **kwargs)

    def _safe_update(self, request, *args, **kwargs):
        ticket = self.get_object()
        u = request.user

        # Support/Admin can update anything
        if u.role in (User.Role.SUPPORT, User.Role.ADMIN):
            return super().update(request, *args, **kwargs)

        # Others can only edit their own ticket
        if ticket.creator_id != u.id:
            raise PermissionDenied("You can only edit your own tickets.")

        # IMPORTANT: customer/contractor must not be able to send response/status via PATCH/PUT
        if "response" in request.data or "status" in request.data:
            raise PermissionDenied("You cannot set ticket response/status.")

        return super().update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        # ✅ فقط پشتیبان/ادمین حذف کند
        u = request.user
        if u.role not in (User.Role.SUPPORT, User.Role.ADMIN):
            raise PermissionDenied("Only support/admin can delete tickets.")
        return super().destroy(request, *args, **kwargs)

    # ✅ پاسخ تیکت: فقط پشتیبان/ادمین + فقط یک بار
    @action(detail=True, methods=["post"], url_path="reply")
    def reply(self, request, pk=None):
     u = request.user
     if u.role not in (User.Role.SUPPORT, User.Role.ADMIN):
        raise PermissionDenied("Only support/admin can reply to tickets.")

     ticket = self.get_object()

     # only one reply allowed
     if getattr(ticket, "support_reply", ""):
         raise ValidationError("This ticket already has a reply.")

     text = request.data.get("support_reply", "")
     if not str(text).strip():
        raise ValidationError({"support_reply": "This field is required."})

     ticket.support_reply = text

     if ticket.status == Ticket.STATUS_OPEN:
         ticket.status = Ticket.STATUS_IN_PROGRESS

     ticket.save()
     return Response(TicketSerializer(ticket).data, status=200)
