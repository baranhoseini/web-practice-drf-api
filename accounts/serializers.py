from django.contrib.auth import get_user_model
from rest_framework import serializers

from ads.models import Ad

User = get_user_model()


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=6)

    class Meta:
        model = User
        fields = ("id", "username", "email", "phone", "role", "password")

    def validate_role(self, value):
        allowed = {User.Role.CUSTOMER, User.Role.CONTRACTOR}
        return value if value in allowed else User.Role.CUSTOMER

    def create(self, validated_data):
        password = validated_data.pop("password")
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user


# -------- Part 15 serializers --------

class PublicUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        # non-sensitive info only
        fields = ("id", "username", "role")


class AdSummarySerializer(serializers.ModelSerializer):
    creator_id = serializers.IntegerField(read_only=True)
    assigned_contractor_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Ad
        fields = (
            "id",
            "title",
            "category",
            "status",
            "creator_id",
            "assigned_contractor_id",
            "scheduled_at",
            "location",
            "contractor_marked_done",
            "created_at",
        )


class MeProfileSerializer(serializers.Serializer):
    user = PublicUserSerializer()
    ads = AdSummarySerializer(many=True)


class ContractorListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    avg_rating = serializers.FloatField()
    review_count = serializers.IntegerField()
    completed_ads_count = serializers.IntegerField()