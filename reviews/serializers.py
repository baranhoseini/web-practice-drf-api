from rest_framework import serializers
from .models import Review


class ReviewSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    contractor_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = ("id", "ad", "contractor_id", "author_id", "text", "rating", "created_at")
        read_only_fields = ("id", "ad", "contractor_id", "author_id", "created_at")

    def validate_rating(self, value):
        if not (1 <= int(value) <= 5):
            raise serializers.ValidationError("Rating must be between 1 and 5.")
        return value
