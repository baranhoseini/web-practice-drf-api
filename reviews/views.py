from django.db.models import Avg, Count
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import NotFound, ValidationError

from accounts.models import User
from .models import Review
from .serializers import ReviewSerializer


class ContractorReviewsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contractor_id):
        try:
            contractor = User.objects.get(id=contractor_id, role=User.Role.CONTRACTOR)
        except User.DoesNotExist:
            raise NotFound("Contractor not found")

        qs = Review.objects.filter(contractor=contractor).order_by("-created_at")

        rating = request.query_params.get("rating")
        min_rating = request.query_params.get("min_rating")

        if rating is not None:
            try:
                rating = int(rating)
            except ValueError:
                raise ValidationError({"rating": "Must be an integer"})
            if rating < 1 or rating > 5:
                raise ValidationError({"rating": "Must be between 1 and 5"})
            qs = qs.filter(rating=rating)

        if min_rating is not None:
            try:
                min_rating = int(min_rating)
            except ValueError:
                raise ValidationError({"min_rating": "Must be an integer"})
            if min_rating < 1 or min_rating > 5:
                raise ValidationError({"min_rating": "Must be between 1 and 5"})
            qs = qs.filter(rating__gte=min_rating)

        return Response({
            "contractor_id": contractor.id,
            "review_count": qs.count(),
            "avg_rating": float(qs.aggregate(avg=Avg("rating"))["avg"] or 0),
            "reviews": ReviewSerializer(qs, many=True).data,
        })
