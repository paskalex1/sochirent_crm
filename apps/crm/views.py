from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from .models import Pipeline, Stage, Deal

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
