from rest_framework import serializers
from .models import Ticket
from accounts.models import User


class TicketSerializer(serializers.ModelSerializer):
    creator_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id",
            "creator_id",
            "ad",
            "title",
            "message",
            "support_reply",
            "status",
            "created_at",
        )
        read_only_fields = (
            "id",
            "creator_id",
            "support_reply",   # کاربر عادی/پیمانکار نمی‌تواند پاسخ بگذارد
            "status",          # کاربر عادی/پیمانکار وضعیت را تغییر ندهد
            "created_at",
        )

    def validate(self, attrs):
        # جلوگیری از این که مشتری/پیمانکار status یا reply بفرستند
        req = self.context.get("request")
        if req and req.user.role not in (User.Role.SUPPORT, User.Role.ADMIN):
            if "status" in req.data or "support_reply" in req.data:
                raise serializers.ValidationError("You cannot set ticket status/reply.")
        return attrs
