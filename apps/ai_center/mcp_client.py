import uuid
from typing import Any, Dict, Optional

try:
    import requests  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover - защита от отсутствия пакета
    requests = None  # type: ignore[assignment]


def _rpc_call(server_url: str, method: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if requests is None:
        raise RuntimeError(
            "Пакет 'requests' не установлен. "
            "Добавьте его в окружение (pip install requests), чтобы вызывать MCP‑серверы."
        )
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }
    response = requests.post(server_url, json=payload, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"MCP error: {data['error']}")
    return data.get("result", {})


def list_tools(server_url: str) -> Dict[str, Any]:
    return _rpc_call(server_url, "tools/list", {})


def call_tool(server_url: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    return _rpc_call(
        server_url,
        "tools/call",
        {
            "name": tool_name,
            "arguments": arguments,
        },
    )
