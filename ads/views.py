from django.db.models import Q
from django.utils.dateparse import parse_datetime

from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound

from accounts.models import User
from .models import Ad, WorkRequest
from .serializers import AdSerializer, WorkRequestSerializer
from .permissions import IsAdOwnerOrSupportAdmin

from reviews.models import Review
from reviews.serializers import ReviewSerializer


class AdViewSet(viewsets.ModelViewSet):
    serializer_class = AdSerializer
    permission_classes = [IsAuthenticated, IsAdOwnerOrSupportAdmin]

    def get_queryset(self):
        user = self.request.user

        if user.role == User.Role.CUSTOMER:
            # customer: see own ads + OPEN ads
            return Ad.objects.filter(Q(creator=user) | Q(status=Ad.Status.OPEN)).distinct()

        if user.role == User.Role.CONTRACTOR:
            # contractor: see OPEN ads + ads assigned to them
            return Ad.objects.filter(Q(status=Ad.Status.OPEN) | Q(assigned_contractor=user)).distinct()

        # support/admin: see all
        return Ad.objects.all()

    def perform_create(self, serializer):
        if self.request.user.role != User.Role.CUSTOMER:
            raise PermissionDenied("Only customers can create ads.")
        serializer.save(creator=self.request.user)

    # -------------------------
    # /api/ads/{id}/requests/
    # -------------------------
    @action(detail=True, methods=["get", "post"], url_path="requests", permission_classes=[IsAuthenticated])
    def requests(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if request.method == "GET":
            if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
                qs = ad.requests.all().order_by("-created_at")
                return Response(WorkRequestSerializer(qs, many=True).data)

            if user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
                qs = ad.requests.all().order_by("-created_at")
                return Response(WorkRequestSerializer(qs, many=True).data)

            if user.role == User.Role.CONTRACTOR:
                qs = ad.requests.filter(contractor=user).order_by("-created_at")
                return Response(WorkRequestSerializer(qs, many=True).data)

            raise PermissionDenied("You cannot view requests for this ad.")

        # POST (contractor creates request)
        if user.role != User.Role.CONTRACTOR:
            raise PermissionDenied("Only contractors can request an ad.")

        if ad.status != Ad.Status.OPEN:
            raise ValidationError("You can only request OPEN ads.")

        message = request.data.get("message", "")

        wr, created = WorkRequest.objects.get_or_create(
            ad=ad,
            contractor=user,
            defaults={"status": WorkRequest.Status.PENDING, "message": message},
        )

        if not created and wr.status in (WorkRequest.Status.REJECTED, WorkRequest.Status.CANCELED):
            wr.status = WorkRequest.Status.PENDING
            wr.message = message
            wr.save(update_fields=["status", "message"])

        return Response(WorkRequestSerializer(wr).data, status=201)

    # -------------------------
    # /api/ads/{id}/assign/
    # Customer chooses contractor + sets scheduled_at + location
    # Body: {"contractor_id": X, "scheduled_at": "...Z", "location": "..."}
    # -------------------------
    @action(detail=True, methods=["post"], url_path="assign", permission_classes=[IsAuthenticated])
    def assign(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        # who can assign?
        if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
            pass
        elif user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
            pass
        else:
            raise PermissionDenied("Only owner/support/admin can assign.")

        if ad.status != Ad.Status.OPEN:
            raise ValidationError("Only OPEN ads can be assigned.")

        contractor_id = request.data.get("contractor_id")
        scheduled_at_raw = request.data.get("scheduled_at")
        location = request.data.get("location")

        if not contractor_id:
            raise ValidationError({"contractor_id": "This field is required."})
        if not scheduled_at_raw:
            raise ValidationError({"scheduled_at": "This field is required."})
        if not location:
            raise ValidationError({"location": "This field is required."})

        scheduled_at = parse_datetime(scheduled_at_raw)
        if scheduled_at is None:
            raise ValidationError({"scheduled_at": "Invalid datetime. Use ISO 8601."})

        try:
            contractor = User.objects.get(id=contractor_id, role=User.Role.CONTRACTOR)
        except User.DoesNotExist:
            raise NotFound("Contractor not found.")

        # contractor must have requested this ad
        try:
            chosen_wr = WorkRequest.objects.get(ad=ad, contractor=contractor)
        except WorkRequest.DoesNotExist:
            raise NotFound("This contractor has not requested this ad.")

        # accept chosen request, reject other pending requests
        WorkRequest.objects.filter(ad=ad).exclude(id=chosen_wr.id).filter(
            status=WorkRequest.Status.PENDING
        ).update(status=WorkRequest.Status.REJECTED)

        chosen_wr.status = WorkRequest.Status.ACCEPTED
        chosen_wr.save(update_fields=["status"])

        ad.assigned_contractor = contractor
        ad.scheduled_at = scheduled_at
        ad.location = location
        ad.status = Ad.Status.ASSIGNED
        ad.contractor_marked_done = False
        ad.save(
            update_fields=[
                "assigned_contractor",
                "scheduled_at",
                "location",
                "status",
                "contractor_marked_done",
            ]
        )

        return Response(AdSerializer(ad).data, status=200)

    # -------------------------
    # /api/ads/{id}/schedule/
    # Bonus 3.3: assigned contractor can update scheduled_at + location
    # - must be ASSIGNED
    # - no time conflicts (same exact time)
    # -------------------------
    @action(detail=True, methods=["post"], url_path="schedule", permission_classes=[IsAuthenticated])
    def schedule(self, request, pk=None):
        ad = self.get_object()
        u = request.user

        if u.role != User.Role.CONTRACTOR:
            raise PermissionDenied("Only contractors can set schedule.")

        if ad.assigned_contractor_id != u.id:
            raise PermissionDenied("Only assigned contractor can schedule this ad.")

        if ad.status != Ad.Status.ASSIGNED:
            raise ValidationError("Only ASSIGNED ads can be scheduled.")

        scheduled_at_raw = request.data.get("scheduled_at")
        location = request.data.get("location")

        if not scheduled_at_raw or not location:
            raise ValidationError({"scheduled_at": "required", "location": "required"})

        dt = parse_datetime(scheduled_at_raw)
        if dt is None:
            raise ValidationError({"scheduled_at": "Use ISO format like 2025-12-30T10:00:00Z"})

        conflict = Ad.objects.filter(
            assigned_contractor=u,
            status=Ad.Status.ASSIGNED,
            scheduled_at=dt,
        ).exclude(id=ad.id).exists()

        if conflict:
            raise ValidationError({"scheduled_at": "Time conflict: you already have a job at this time."})

        ad.scheduled_at = dt
        ad.location = location
        ad.save(update_fields=["scheduled_at", "location"])

        return Response(AdSerializer(ad).data, status=200)

    # -------------------------
    # /api/ads/{id}/contractor-done/
    # assigned contractor marks done
    # -------------------------
    @action(detail=True, methods=["post"], url_path="contractor-done", permission_classes=[IsAuthenticated])
    def contractor_done(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if user.role != User.Role.CONTRACTOR:
            raise PermissionDenied("Only contractors can do this.")

        if ad.assigned_contractor_id != user.id:
            raise PermissionDenied("You are not assigned to this ad.")

        if ad.status != Ad.Status.ASSIGNED:
            raise ValidationError("Only ASSIGNED ads can be marked done.")

        ad.contractor_marked_done = True
        ad.save(update_fields=["contractor_marked_done"])
        return Response({"detail": "Marked done by contractor."}, status=200)

    # -------------------------
    # /api/ads/{id}/confirm-done/
    # owner confirms -> DONE
    # -------------------------
    @action(detail=True, methods=["post"], url_path="confirm-done", permission_classes=[IsAuthenticated])
    def confirm_done(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
            pass
        elif user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
            pass
        else:
            raise PermissionDenied("Only owner/support/admin can confirm done.")

        if ad.status != Ad.Status.ASSIGNED:
            raise ValidationError("Only ASSIGNED ads can be confirmed done.")

        if not ad.contractor_marked_done:
            raise ValidationError("Contractor has not marked done yet.")

        ad.status = Ad.Status.DONE
        ad.save(update_fields=["status"])
        return Response({"detail": "Ad confirmed done."}, status=200)

    # -------------------------
    # /api/ads/{id}/cancel/
    # owner/support/admin can cancel (not if DONE)
    # -------------------------
    @action(detail=True, methods=["post"], url_path="cancel", permission_classes=[IsAuthenticated])
    def cancel(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if ad.status == Ad.Status.DONE:
            raise ValidationError("Cannot cancel a DONE ad.")

        if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
            ad.status = Ad.Status.CANCELED
            ad.save(update_fields=["status"])
            return Response({"detail": "Ad canceled."}, status=200)

        if user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
            ad.status = Ad.Status.CANCELED
            ad.save(update_fields=["status"])
            return Response({"detail": "Ad canceled."}, status=200)

        raise PermissionDenied("You cannot cancel this ad.")

    # -------------------------
    # /api/ads/{id}/review/
    # Customer can review assigned contractor ONLY if ad is DONE
    # Body: {"rating": 1..5, "text": "..."}
    # -------------------------
    @action(detail=True, methods=["post"], url_path="review", permission_classes=[IsAuthenticated])
    def review(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
            pass
        elif user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
            pass
        else:
            raise PermissionDenied("Only the ad owner (customer) can review.")

        if ad.status != Ad.Status.DONE:
            raise ValidationError("You can only review after the ad is DONE.")

        if not ad.assigned_contractor_id:
            raise ValidationError("This ad has no assigned contractor.")

        if Review.objects.filter(ad=ad, author_id=user.id).exists():
            raise ValidationError("You already reviewed this ad.")

        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = Review.objects.create(
            ad=ad,
            contractor_id=ad.assigned_contractor_id,
            author=user,
            text=serializer.validated_data.get("text", ""),
            rating=serializer.validated_data["rating"],
        )
        return Response(ReviewSerializer(review).data, status=201)

    # -------------------------
    # /api/ads/{id}/reviews/
    # View reviews for this ad:
    # - owner/support/admin sees all
    # - assigned contractor sees all
    # -------------------------
    @action(detail=True, methods=["get"], url_path="reviews", permission_classes=[IsAuthenticated])
    def reviews(self, request, pk=None):
        ad = self.get_object()
        user = request.user

        if user.role in (User.Role.SUPPORT, User.Role.ADMIN):
            qs = Review.objects.filter(ad=ad).order_by("-created_at")
            return Response(ReviewSerializer(qs, many=True).data)

        if user.role == User.Role.CUSTOMER and ad.creator_id == user.id:
            qs = Review.objects.filter(ad=ad).order_by("-created_at")
            return Response(ReviewSerializer(qs, many=True).data)

        if user.role == User.Role.CONTRACTOR and ad.assigned_contractor_id == user.id:
            qs = Review.objects.filter(ad=ad).order_by("-created_at")
            return Response(ReviewSerializer(qs, many=True).data)

        raise PermissionDenied("You cannot view reviews for this ad.")


class WorkRequestViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]
    serializer_class = WorkRequestSerializer

    # POST /api/requests/{id}/cancel/
    @action(detail=True, methods=["post"], url_path="cancel")
    def cancel(self, request, pk=None):
        try:
            wr = WorkRequest.objects.get(pk=pk)
        except WorkRequest.DoesNotExist:
            raise NotFound("Work request not found")

        if request.user.role != User.Role.CONTRACTOR or wr.contractor_id != request.user.id:
            raise PermissionDenied("You can only cancel your own request")

        if wr.status not in (WorkRequest.Status.PENDING, WorkRequest.Status.ACCEPTED):
            raise ValidationError("This request cannot be canceled now.")

        wr.status = WorkRequest.Status.CANCELED
        wr.save(update_fields=["status"])
        return Response({"detail": "Cancelled"}, status=200)
