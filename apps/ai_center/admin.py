from django import forms
from django.contrib import admin

from .models import AiSettings, Agent, Conversation, MCPServer, Message


class AiSettingsForm(forms.ModelForm):
    openai_api_key = forms.CharField(
        label="OpenAI API key",
        widget=forms.PasswordInput(render_value=False),
        required=False,
        help_text="Ключ будет сохранён в базе. В продакшене лучше хранить его в переменных окружения.",
    )

    class Meta:
        model = AiSettings
        fields = ["openai_api_key"]

    def clean_openai_api_key(self):
        value = self.cleaned_data.get("openai_api_key")
        # Если редактируем существующую запись и поле оставили пустым —
        # сохраняем старое значение.
        if not value and self.instance and self.instance.pk:
            return self.instance.openai_api_key
        return value


@admin.register(AiSettings)
class AiSettingsAdmin(admin.ModelAdmin):
    form = AiSettingsForm
    list_display = ("id", "created_at", "updated_at")

    def has_add_permission(self, request):
        # Разрешаем создать только одну запись настроек.
        if AiSettings.objects.exists():
            return False
        return super().has_add_permission(request)


@admin.register(MCPServer)
class MCPServerAdmin(admin.ModelAdmin):
    list_display = ("name", "base_url", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "base_url", "description")


@admin.register(Agent)
class AgentAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "model_name", "is_active", "created_at")
    list_filter = ("is_active", "mcp_servers")
    search_fields = ("name", "slug", "description", "model_name")
    prepopulated_fields = {"slug": ("name",)}
    filter_horizontal = ("mcp_servers",)


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("id", "agent", "title", "session_id", "created_at")
    search_fields = ("title", "session_id", "agent__name")
    list_filter = ("agent",)


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("id", "conversation", "role", "tool_name", "created_at")
    list_filter = ("role", "tool_name")
    search_fields = ("content", "tool_name", "conversation__session_id")
