from django.contrib import admin
from django.urls import include, path
from rest_framework.routers import DefaultRouter

from apps.bookings.api import (
    BookingViewSet,
    CalendarEventViewSet,
    GuestViewSet,
    RatePlanViewSet,
)
from apps.crm.api import DealViewSet, LeadViewSet, PipelineViewSet, StageViewSet
from apps.crm.views import dashboard_view
from apps.ai.api import MaintenanceTaskAIAnalyzeView, ReviewAnalyzeView
from apps.owners.api import OwnerViewSet
from apps.owners.extranet_api import OwnerDashboardView, OwnerReportsView
from apps.revenue.api import PriceRecommendationListView, PriceSuggestionView
from apps.properties.api import (
    GMDashboardView,
    PropertyManagerDashboardView,
    PropertyViewSet,
    UnitViewSet,
)
from apps.finance.api import (
    ExpenseViewSet,
    FinanceRecordViewSet,
    FinanceSummaryView,
    OwnerReportViewSet,
    PayoutViewSet,
)
from apps.operations.api import (
    CheckinTaskViewSet,
    CheckoutTaskViewSet,
    CleaningTaskViewSet,
    MaintenanceTaskViewSet,
    OwnerRequestTaskViewSet,
    QualityInspectionTaskViewSet,
    MaintenanceSLAReportView,
)

router = DefaultRouter()
router.register(r"leads", LeadViewSet, basename="lead")
router.register(r"deals", DealViewSet, basename="deal")
router.register(r"pipelines", PipelineViewSet, basename="pipeline")
router.register(r"stages", StageViewSet, basename="stage")
router.register(r"owners", OwnerViewSet, basename="owner")
router.register(r"properties", PropertyViewSet, basename="property")
router.register(r"units", UnitViewSet, basename="unit")
router.register(r"guests", GuestViewSet, basename="guest")
router.register(r"rate-plans", RatePlanViewSet, basename="rateplan")
router.register(r"bookings", BookingViewSet, basename="booking")
router.register(r"calendar-events", CalendarEventViewSet, basename="calendarevent")
router.register(r"tasks/cleaning", CleaningTaskViewSet, basename="cleaningtask")
router.register(r"tasks/maintenance", MaintenanceTaskViewSet, basename="maintenancetask")
router.register(r"tasks/checkin", CheckinTaskViewSet, basename="checkintask")
router.register(r"tasks/checkout", CheckoutTaskViewSet, basename="checkouttask")
router.register(
    r"tasks/quality-inspection",
    QualityInspectionTaskViewSet,
    basename="qualityinspectiontask",
)
router.register(
    r"tasks/owner-request",
    OwnerRequestTaskViewSet,
    basename="ownerrequesttask",
)
router.register(r"finance-records", FinanceRecordViewSet, basename="financerecord")
router.register(r"expenses", ExpenseViewSet, basename="expense")
router.register(r"payouts", PayoutViewSet, basename="payout")
router.register(r"owner-reports", OwnerReportViewSet, basename="ownerreport")

urlpatterns = [
    path("", dashboard_view, name="dashboard"),
    path("admin/", admin.site.urls),
    path("crm/", include("apps.crm.urls")),
    path("accounts/", include("apps.accounts.urls")),
    path("api/v1/gm-dashboard/", GMDashboardView.as_view(), name="gm-dashboard"),
    path(
        "api/v1/extranet/owner/dashboard/",
        OwnerDashboardView.as_view(),
        name="owner-extranet-dashboard",
    ),
    path(
        "api/v1/extranet/owner/reports/",
        OwnerReportsView.as_view(),
        name="owner-extranet-reports",
    ),
    path(
        "api/v1/property-manager/dashboard/",
        PropertyManagerDashboardView.as_view(),
        name="property-manager-dashboard",
    ),
    path(
        "api/v1/ai/reviews/analyze/",
        ReviewAnalyzeView.as_view(),
        name="ai-review-analyze",
    ),
    path(
        "api/v1/ai/tasks/maintenance/<int:pk>/analyze/",
        MaintenanceTaskAIAnalyzeView.as_view(),
        name="ai-maintenance-task-analyze",
    ),
    path(
        "api/v1/revenue/price-suggestion/",
        PriceSuggestionView.as_view(),
        name="revenue-price-suggestion",
    ),
    path(
        "api/v1/revenue/price-recommendations/",
        PriceRecommendationListView.as_view(),
        name="revenue-price-recommendations",
    ),
    path("api/v1/", include(router.urls)),
    path("api/v1/finance-summary/", FinanceSummaryView.as_view(), name="finance-summary"),
    path("api/v1/maintenance-sla/", MaintenanceSLAReportView.as_view(), name="maintenance-sla"),
]
