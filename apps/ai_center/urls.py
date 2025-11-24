from django.urls import path

from . import views


app_name = "ai_center"

urlpatterns = [
    path("agents/", views.AgentListView.as_view(), name="agent_list"),
    path("agents/<slug:slug>/chat/", views.agent_chat_start, name="agent_chat_start"),
    path("agents/<slug:slug>/chat/<str:session_id>/", views.agent_chat, name="agent_chat"),
]

