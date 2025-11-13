from django.urls import path
from . import views

app_name = "crm"
urlpatterns = [
    path("kanban/<str:pipeline_code>/", views.kanban_view, name="kanban"),
    path("deal/<int:deal_id>/move/", views.move_deal, name="move_deal"),
]
