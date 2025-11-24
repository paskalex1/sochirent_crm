import uuid

from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.generic import ListView

from .agent_engine import run_agent
from .models import Agent, Conversation


@method_decorator(staff_member_required, name="dispatch")
class AgentListView(ListView):
    model = Agent
    template_name = "ai_center/agent_list.html"
    context_object_name = "agents"


@staff_member_required
def agent_chat_start(request, slug: str):
    """
    Создаёт новый диалог с агентом и редиректит на страницу чата.
    """
    agent = get_object_or_404(Agent, slug=slug, is_active=True)
    session_id = uuid.uuid4().hex
    conversation = Conversation.objects.create(
        agent=agent,
        session_id=session_id,
        title=f"Диалог с {agent.name}",
    )
    return redirect(
        reverse(
            "ai_center:agent_chat",
            kwargs={"slug": agent.slug, "session_id": conversation.session_id},
        )
    )


@staff_member_required
def agent_chat(request, slug: str, session_id: str):
    """
    Страница чата с конкретным агентом и сессией.
    """
    agent = get_object_or_404(Agent, slug=slug, is_active=True)
    conversation = get_object_or_404(
        Conversation,
        agent=agent,
        session_id=session_id,
    )

    if request.method == "POST":
        user_message_text = request.POST.get("message", "").strip()
        if user_message_text:
            run_agent(agent, conversation, user_message_text)
        return redirect(
            reverse(
                "ai_center:agent_chat",
                kwargs={"slug": agent.slug, "session_id": conversation.session_id},
            )
        )

    messages = conversation.messages.order_by("created_at")
    return render(
        request,
        "ai_center/agent_chat.html",
        {
            "agent": agent,
            "conversation": conversation,
            "messages": messages,
        },
    )

