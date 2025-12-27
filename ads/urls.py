from rest_framework.routers import DefaultRouter
from .views import AdViewSet, WorkRequestViewSet

router = DefaultRouter()
router.register("ads", AdViewSet, basename="ads")
router.register("requests", WorkRequestViewSet, basename="requests")

urlpatterns = router.urls
