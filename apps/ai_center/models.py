import uuid

from django.db import models


def generate_session_id() -> str:
    """
    Генерация строкового идентификатора сессии (UUID4 hex).
    """
    return uuid.uuid4().hex


class AiSettings(models.Model):
    """
    Глобальные настройки AI / OpenAI.
    Хранит API‑ключ, задаваемый через админку.

    Для продакшена предпочтительно хранить ключи в переменных окружения,
    а модель использовать как удобный UI‑слой.
    """

    openai_api_key = models.CharField(
        "OpenAI API key",
        max_length=255,
        blank=True,
        help_text=(
            "Ключ для OpenAI Chat API. "
            "Используется только в режиме DEBUG=True. "
            "В продакшене ключ должен быть задан через переменную окружения "
            "OPENAI_API_KEY или в settings.OPENAI_API_KEY."
        ),
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "AI‑настройки"
        verbose_name_plural = "AI‑настройки"

    def __str__(self) -> str:
        return "AI‑настройки"


class MCPServer(models.Model):
    """
    MCP‑сервер, предоставляющий набор инструментов.
    """

    name = models.CharField("Имя сервера", max_length=255, unique=True)
    base_url = models.URLField(
        "Базовый URL MCP",
        max_length=500,
        help_text="Например: http://localhost:3001/mcp",
    )
    description = models.TextField("Описание", blank=True)
    is_active = models.BooleanField("Активен", default=True)
    tools_config = models.JSONField(
        "Конфигурация инструментов",
        default=dict,
        blank=True,
        help_text=(
            "JSON c описанием инструментов этого MCP‑сервера. "
            "Например: {\"tools\": [{\"name\": \"read_file\", ...}]}"
        ),
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "MCP‑сервер"
        verbose_name_plural = "MCP‑серверы"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Agent(models.Model):
    """
    Описание AI-агента.
    """

    name = models.CharField("Имя агента", max_length=255, unique=True)
    slug = models.SlugField("Слаг", unique=True)
    description = models.TextField("Описание", blank=True)
    system_prompt = models.TextField("Системный промпт", blank=True)
    model_name = models.CharField(
        "Модель",
        max_length=100,
        default="gpt-4.1-mini",
        help_text="Например: gpt-5.1, gpt-4.1-mini и т.п.",
    )
    is_active = models.BooleanField("Активен", default=True)
    tools_config = models.JSONField("Конфигурация инструментов", default=dict, blank=True)
    mcp_servers = models.ManyToManyField(
        MCPServer,
        verbose_name="MCP‑серверы",
        related_name="agents",
        blank=True,
        help_text="К каким MCP‑серверам имеет доступ этот агент.",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "AI-агент"
        verbose_name_plural = "AI-агенты"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Conversation(models.Model):
    """
    Сессия общения с агентом.
    """

    agent = models.ForeignKey(
        Agent,
        on_delete=models.CASCADE,
        related_name="conversations",
        verbose_name="Агент",
    )
    title = models.CharField("Заголовок", max_length=255, blank=True)
    session_id = models.CharField(
        "ID сессии",
        max_length=64,
        unique=True,
        default=generate_session_id,
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Диалог"
        verbose_name_plural = "Диалоги"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.title or f"Диалог с {self.agent.name} ({self.session_id})"


class Message(models.Model):
    """
    Отдельное сообщение в диалоге.
    """

    ROLE_USER = "user"
    ROLE_ASSISTANT = "assistant"
    ROLE_TOOL = "tool"
    ROLE_SYSTEM = "system"

    ROLE_CHOICES = [
        (ROLE_USER, "Пользователь"),
        (ROLE_ASSISTANT, "Ассистент"),
        (ROLE_TOOL, "Инструмент"),
        (ROLE_SYSTEM, "Система"),
    ]

    conversation = models.ForeignKey(
        Conversation,
        on_delete=models.CASCADE,
        related_name="messages",
        verbose_name="Диалог",
    )
    role = models.CharField("Роль", max_length=20, choices=ROLE_CHOICES)
    content = models.TextField("Содержимое")
    tool_name = models.CharField("Имя инструмента", max_length=255, blank=True, null=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        ordering = ["created_at"]

    def __str__(self) -> str:
        return f"{self.role}: {self.content[:60]}"
