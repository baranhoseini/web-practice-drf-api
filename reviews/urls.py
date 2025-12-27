from django.urls import path
from .views import ContractorReviewsAPIView

urlpatterns = [
    path("contractors/<int:contractor_id>/reviews/", ContractorReviewsAPIView.as_view()),
]
