from rest_framework import serializers
from .models import Ad, WorkRequest


class AdSerializer(serializers.ModelSerializer):
    creator_id = serializers.IntegerField(read_only=True)
    assigned_contractor_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ad
        fields = (
            "id", "title", "description", "category",
            "status", "creator_id", "assigned_contractor_id",
            "scheduled_at", "location",
            "contractor_marked_done", "created_at",
        )
        read_only_fields = (
            "status", "creator_id", "assigned_contractor_id",
            "scheduled_at", "location",
            "contractor_marked_done", "created_at",
        )


class WorkRequestSerializer(serializers.ModelSerializer):
    contractor_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = WorkRequest
        fields = ("id", "ad", "contractor_id", "message", "status", "created_at")
        read_only_fields = ("contractor_id", "status", "created_at")
