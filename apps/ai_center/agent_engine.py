import json
from typing import Any, Dict, List

from django.conf import settings

from . import mcp_client
from .models import AiSettings, Agent, Conversation, MCPServer, Message


def build_openai_messages(agent: Agent, conversation: Conversation) -> List[Dict[str, Any]]:
    """
    Собирает историю переписки в формат OpenAI Chat API.
    """
    messages: List[Dict[str, Any]] = []

    if agent.system_prompt:
        messages.append({"role": "system", "content": agent.system_prompt})

    for msg in conversation.messages.order_by("created_at"):
        messages.append(
            {
                "role": msg.role,
                "content": msg.content,
            }
        )

    return messages


def get_tools_for_agent(agent: Agent) -> List[Dict[str, Any]]:
    """
    Преобразует Agent.tools_config в список tools для OpenAI.

    Ожидаемый формат Agent.tools_config:
    {
      "filesystem": {
        "server_url": "http://localhost:3001/mcp",
        "tools": [
          {"name": "read_file", "description": "...", "parameters": {...}}
        ]
      }
    }
    """
    tools: List[Dict[str, Any]] = []

    # 1) Собираем инструменты со всех активных MCP‑серверов, привязанных к агенту.
    servers: List[MCPServer] = list(agent.mcp_servers.filter(is_active=True))
    for server in servers:
        cfg = server.tools_config or {}
        if isinstance(cfg, dict):
            tools_list = cfg.get("tools", [])
        else:
            tools_list = cfg

        for tool in tools_list:
            tools.append(
                {
                    "type": "function",
                    "function": tool,
                }
            )

    # 2) Backward‑compat: если MCP‑серверов нет, пробуем старый формат Agent.tools_config.
    if not tools:
        cfg = agent.tools_config or {}
        for source_cfg in cfg.values():
            for tool in source_cfg.get("tools", []):
                tools.append(
                    {
                        "type": "function",
                        "function": tool,
                    }
                )

    return tools


def _find_mcp_config_for_tool(agent: Agent, tool_name: str) -> Dict[str, Any] | None:
    """
    Находит MCP-конфиг (server_url, tool spec) для указанного имени инструмента.

    Сначала ищет среди MCP‑серверов, привязанных к агенту, затем (для
    обратной совместимости) в Agent.tools_config.
    """
    # 1) Поиск среди привязанных MCP‑серверов.
    for server in agent.mcp_servers.filter(is_active=True):
        cfg = server.tools_config or {}
        if isinstance(cfg, dict):
            tools_list = cfg.get("tools", [])
        else:
            tools_list = cfg

        for tool in tools_list:
            if tool.get("name") == tool_name:
                return {
                    "source": server.name,
                    "server_url": server.base_url,
                    "tool": tool,
                }

    # 2) Backward‑compat: старый формат в Agent.tools_config.
    cfg = agent.tools_config or {}
    for source_name, source_cfg in cfg.items():
        for tool in source_cfg.get("tools", []):
            if tool.get("name") == tool_name:
                return {
                    "source": source_name,
                    "server_url": source_cfg.get("server_url"),
                    "tool": tool,
                }
    return None


def run_agent(agent: Agent, conversation: Conversation, user_message_text: str) -> Message:
    """
    Добавляет сообщение пользователя, вызывает OpenAI с tools,
    при необходимости вызывает MCP-инструменты и возвращает финальное сообщение ассистента.

    TODO:
    - более аккуратное управление историей (обрезка / summary)
    - расширенная обработка tool calling (несколько раундов)
    """
    user_message_text = user_message_text.strip()
    if not user_message_text:
        raise ValueError("Пустое сообщение пользователя.")

    Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_USER,
        content=user_message_text,
    )

    messages = build_openai_messages(agent, conversation)
    tools = get_tools_for_agent(agent)

    try:
        from openai import OpenAI  # type: ignore[import-untyped]
    except ImportError as exc:  # pragma: no cover - защита от отсутствия пакета
        raise RuntimeError(
            "Пакет 'openai' не установлен. "
            "Добавьте его в окружение (pip install openai), чтобы использовать AI Center."
        ) from exc

    # Источник API‑ключа:
    # 1) settings.OPENAI_API_KEY (если задан),
    # 2) (только при DEBUG=True) последняя запись AiSettings в базе,
    # 3) переменная окружения OPENAI_API_KEY (если ничего не указано явно).
    api_key = getattr(settings, "OPENAI_API_KEY", None)
    debug_mode = getattr(settings, "DEBUG", False)

    # В режиме разработки можно хранить ключ в БД, в продакшене — только в env/settings.
    if debug_mode and not api_key:
        settings_row = AiSettings.objects.order_by("-id").first()
        if settings_row and settings_row.openai_api_key:
            api_key = settings_row.openai_api_key

    client = OpenAI(api_key=api_key) if api_key else OpenAI()

    response = client.chat.completions.create(
        model=agent.model_name,
        messages=messages,
        tools=tools or None,
        tool_choice="auto" if tools else "none",
    )

    choice = response.choices[0]
    msg = choice.message

    tool_calls = getattr(msg, "tool_calls", None) or []

    # Если модель запросила вызов инструментов — делаем один раунд tool calling.
    if tool_calls:
        tool_result_messages: List[Dict[str, Any]] = []

        # Сохраняем "сырой" assistant с tool_calls для истории (можно расширить при необходимости)
        Message.objects.create(
            conversation=conversation,
            role=Message.ROLE_ASSISTANT,
            content=json.dumps(
                {
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        }
                        for tc in tool_calls
                    ]
                },
                ensure_ascii=False,
            ),
        )

        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            raw_args = tool_call.function.arguments or "{}"

            try:
                parsed_args = json.loads(raw_args)
            except json.JSONDecodeError:
                parsed_args = {}

            mcp_cfg = _find_mcp_config_for_tool(agent, tool_name)
            server_url = (mcp_cfg or {}).get("server_url")

            if not server_url:
                tool_result: Dict[str, Any] = {
                    "error": f"No MCP server configured for tool '{tool_name}'"
                }
            else:
                try:
                    tool_result = mcp_client.call_tool(server_url, tool_name, parsed_args)
                except Exception as exc:  # noqa: BLE001
                    tool_result = {"error": f"MCP call failed: {exc!r}"}

            Message.objects.create(
                conversation=conversation,
                role=Message.ROLE_TOOL,
                tool_name=tool_name,
                content=json.dumps(tool_result, ensure_ascii=False),
            )

            tool_result_messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

        # Второй запрос с результатами инструментов.
        followup_messages = messages + [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in tool_calls
                ],
            },
            *tool_result_messages,
        ]

        response = client.chat.completions.create(
            model=agent.model_name,
            messages=followup_messages,
        )
        choice = response.choices[0]
        msg = choice.message

    assistant_message = Message.objects.create(
        conversation=conversation,
        role=Message.ROLE_ASSISTANT,
        content=msg.content or "",
    )

    return assistant_message
