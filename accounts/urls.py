from django.urls import path
from .views import MyScheduleAPIView, UserRolesAPIView
from .views import RegisterView, LoginView, ContractorProfileAPIView
from .views import MeProfileAPIView
from .views import ContractorsListAPIView

urlpatterns = [
    path("auth/register/", RegisterView.as_view()),
    path("auth/login/", LoginView.as_view()),
    path("me/profile/", MeProfileAPIView.as_view()),
    path("me/schedule/", MyScheduleAPIView.as_view()),

    path("contractors/", ContractorsListAPIView.as_view()),
    path("users/<int:user_id>/roles/", UserRolesAPIView.as_view()),
    path("contractors/<int:contractor_id>/profile/", ContractorProfileAPIView.as_view()),
]

