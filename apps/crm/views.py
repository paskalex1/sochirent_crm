from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from .models import Deal, Pipeline, Stage


@login_required
def dashboard_view(request):
    """
    Главная страница CRM после входа.
    Пока содержит ссылки на основные разделы.
    """
    return render(request, "crm/dashboard.html")


@login_required
def kanban_view(request, pipeline_code="onboarding"):
    pipeline = get_object_or_404(Pipeline, code=pipeline_code)
    stages = pipeline.stages.all().prefetch_related("deals")
    return render(request, "crm/kanban.html", {"pipeline": pipeline, "stages": stages})

@require_POST
def move_deal(request, deal_id):
    deal = get_object_or_404(Deal, pk=deal_id)
    stage_id = request.POST.get("stage_id")
    stage = get_object_or_404(Stage, pk=stage_id, pipeline=deal.pipeline)
    deal.stage = stage
    deal.save(update_fields=["stage", "updated_at"])
    return JsonResponse({"status": "ok"})
