from django.contrib import admin
from django.urls import path, include
from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from apps.crm.api import LeadViewSet, DealViewSet, PipelineViewSet, StageViewSet
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("crm/", include("apps.crm.urls")),
]

router = DefaultRouter()
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"pipelines", PipelineViewSet, basename="pipeline")
router.register(r"stages", StageViewSet, basename="stage")

urlpatterns = [
    path("admin/", admin.site.urls),
    path("crm/", include("apps.crm.urls")),
    path("api/v1/", include(router.urls)),
    path("api/v1/auth/jwt/create/", TokenObtainPairView.as_view(), name="jwt-create"),
    path("api/v1/auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
]
