# accounts/views.py

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password
from django.db.models import Q, Avg, Count
from django.db.models import OuterRef, Subquery, IntegerField, FloatField, Count, Avg
from django.db.models.functions import Coalesce

from rest_framework import status, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import NotFound

from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema, OpenApiResponse

from ads.models import Ad
from reviews.models import Review
from reviews.serializers import ReviewSerializer

from .serializers import RegisterSerializer, PublicUserSerializer, AdSummarySerializer


from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from django.contrib.auth.models import Group

from accounts.models import User
from accounts.utils import has_role

from django.utils.dateparse import parse_date



from ads.serializers import AdSerializer  # or AdSummarySerializer


User = get_user_model()


class LoginRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField()


class TokenResponseSerializer(serializers.Serializer):
    refresh = serializers.CharField()
    access = serializers.CharField()


class RegisterView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=RegisterSerializer,
        responses={201: RegisterSerializer},
    )
    def post(self, request):
        ser = RegisterSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        user = ser.save()
        return Response(RegisterSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        request=LoginRequestSerializer,
        responses={
            200: TokenResponseSerializer,
            401: OpenApiResponse(description="Invalid credentials"),
        },
    )
    def post(self, request):
        identifier = request.data.get("identifier")
        password = request.data.get("password")

        if not identifier or not password:
            return Response(
                {"detail": "identifier and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = User.objects.filter(
            Q(username=identifier) | Q(email=identifier) | Q(phone=identifier)
        ).first()

        if not user or not check_password(password, user.password):
            return Response({"detail": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response(
            {"refresh": str(refresh), "access": str(refresh.access_token)},
            status=status.HTTP_200_OK,
        )


class ContractorProfileAPIView(APIView):
    """
    Part 14.2:
    Public contractor profile, includes live aggregates + reviews ordered by time.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, contractor_id):
        try:
            contractor = User.objects.get(id=contractor_id, role=User.Role.CONTRACTOR)
        except User.DoesNotExist:
            raise NotFound("Contractor not found")

        completed_ads_count = Ad.objects.filter(
            assigned_contractor=contractor, status=Ad.Status.DONE
        ).count()

        agg = Review.objects.filter(contractor=contractor).aggregate(
            avg_rating=Avg("rating"),
            review_count=Count("id"),
        )

        reviews = Review.objects.filter(contractor=contractor).order_by("-created_at")

        return Response(
            {
                "id": contractor.id,
                "username": contractor.username,
                "role": contractor.role,
                "completed_ads_count": completed_ads_count,
                "avg_rating": float(agg["avg_rating"] or 0),
                "review_count": agg["review_count"],
                "reviews": ReviewSerializer(reviews, many=True).data,
            }
        )


class MeProfileAPIView(APIView):
    """
    Part 15:
    - Customer: profile + ads they created
    - Contractor: profile + DONE ads they performed (assigned to them)
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user

        # Non-sensitive user info
        user_data = PublicUserSerializer(u).data

        if u.role == User.Role.CUSTOMER:
            qs = Ad.objects.filter(creator=u).order_by("-created_at")

        elif u.role == User.Role.CONTRACTOR:
            qs = Ad.objects.filter(
                assigned_contractor=u,
                status=Ad.Status.DONE,
            ).order_by("-created_at")

        else:
            # Safe default for SUPPORT/ADMIN (customize if you want)
            qs = Ad.objects.filter(creator=u).order_by("-created_at")

        return Response(
            {
                "user": user_data,
                "ads": AdSummarySerializer(qs, many=True).data,
            }
        )


class ContractorsListAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # query params
        min_avg = request.query_params.get("min_avg_rating")
        min_reviews = request.query_params.get("min_review_count")
        ordering = request.query_params.get("ordering", "-avg_rating,-review_count")

        # subqueries for aggregates (works even if no related_name)
        avg_sub = (
            Review.objects.filter(contractor_id=OuterRef("pk"))
            .values("contractor_id")
            .annotate(a=Avg("rating"))
            .values("a")[:1]
        )

        count_sub = (
            Review.objects.filter(contractor_id=OuterRef("pk"))
            .values("contractor_id")
            .annotate(c=Count("id"))
            .values("c")[:1]
        )

        done_count_sub = (
            Ad.objects.filter(assigned_contractor_id=OuterRef("pk"), status=Ad.Status.DONE)
            .values("assigned_contractor_id")
            .annotate(c=Count("id"))
            .values("c")[:1]
        )

        qs = (
            User.objects.filter(role=User.Role.CONTRACTOR)
            .annotate(
                avg_rating=Coalesce(Subquery(avg_sub, output_field=FloatField()), 0.0),
                review_count=Coalesce(Subquery(count_sub, output_field=IntegerField()), 0),
                completed_ads_count=Coalesce(Subquery(done_count_sub, output_field=IntegerField()), 0),
            )
        )

        # filters
        if min_avg is not None:
            qs = qs.filter(avg_rating__gte=float(min_avg))
        if min_reviews is not None:
            qs = qs.filter(review_count__gte=int(min_reviews))

        # ordering (safe allow-list)
        allowed = {"avg_rating", "review_count", "completed_ads_count", "id", "username"}
        order_fields = []
        for part in ordering.split(","):
            part = part.strip()
            if not part:
                continue
            key = part[1:] if part.startswith("-") else part
            if key in allowed:
                order_fields.append(part)

        if order_fields:
            qs = qs.order_by(*order_fields)
        else:
            qs = qs.order_by("-avg_rating", "-review_count")

        data = qs.values("id", "username", "avg_rating", "review_count", "completed_ads_count")
        return Response(list(data))



class UserRolesAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if not has_role(request.user, ["ADMIN"]):
            raise PermissionDenied("Only ADMIN can change roles.")

        roles = request.data.get("roles")
        if not isinstance(roles, list) or not roles:
            raise ValidationError({"roles": "Must be a non-empty list like ['SUPPORT']"})

        allowed = {"CUSTOMER", "CONTRACTOR", "SUPPORT", "ADMIN"}
        bad = [r for r in roles if r not in allowed]
        if bad:
            raise ValidationError({"roles": f"Invalid roles: {bad}"})

        try:
            u = User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFound("User not found")

        groups = list(Group.objects.filter(name__in=roles))
        u.groups.set(groups)

        # (optional) keep your old single role field in sync
        u.role = roles[0]
        u.save(update_fields=["role"])

        return Response({"user_id": u.id, "roles": roles})



class MyScheduleAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        u = request.user
        if u.role != User.Role.CONTRACTOR:
            raise PermissionDenied("Only contractors have a schedule.")

        date_str = request.query_params.get("date")
        if not date_str:
            raise ValidationError({"date": "required, format YYYY-MM-DD"})

        d = parse_date(date_str)
        if d is None:
            raise ValidationError({"date": "invalid date format YYYY-MM-DD"})

        qs = Ad.objects.filter(
            assigned_contractor=u,
            status=Ad.Status.ASSIGNED,
            scheduled_at__date=d,
        ).order_by("scheduled_at")

        return Response({
            "date": date_str,
            "count": qs.count(),
            "items": AdSerializer(qs, many=True).data,
        })
