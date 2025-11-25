import logging
from typing import Any, Dict

from django.conf import settings

try:
    from openai import OpenAI  # type: ignore[import-untyped]
except Exception:  # pragma: no cover - защита от отсутствия пакета
    OpenAI = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)


def _get_openai_client() -> OpenAI:
    """
    Возвращает сконфигурированный OpenAI‑клиент.

    Ключ берётся из settings.OPENAI_API_KEY / переменных окружения.
    """
    if OpenAI is None:
        raise RuntimeError(
            "Пакет 'openai' не установлен. "
            "Добавьте его в окружение (pip install openai), чтобы использовать AI‑сервисы."
        )

    api_key = getattr(settings, "OPENAI_API_KEY", None)
    if api_key:
        return OpenAI(api_key=api_key)
    return OpenAI()


def _get_default_model() -> str:
    """
    Возвращает имя модели по умолчанию для AI‑аналитики задач/отзывов.
    """
    return getattr(settings, "OPENAI_MODEL_NAME", "gpt-5.1")


class AIClient:
    """
    Обёртка над OpenAI Chat Completions для анализа отзывов и задач.
    """

    def __init__(self) -> None:
        self.client = _get_openai_client()
        self.model_name = _get_default_model()

    def analyze_review(self, text: str) -> Dict[str, Any]:
        """
        Анализирует текст отзыва/жалобы гостя.

        Возвращает словарь:
        {
          "sentiment": "positive|neutral|negative",
          "categories": [...],
          "summary": "...",
          "suggestions": "..."
        }
        """
        prompt = (
            "Ты — ассистент службы качества отеля.\n"
            "Проанализируй текст отзыва гостя и ответь строгим JSON без комментариев:\n"
            "{\n"
            '  "sentiment": "positive|neutral|negative",\n'
            '  "categories": ["..."],\n'
            '  "summary": "краткое резюме по-русски",\n'
            '  "suggestions": "что стоит предпринять (по-русски)"\n'
            "}\n"
            "Если чего-то не хватает в тексте, делай лучшие разумные предположения.\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI analyze_review failed: %r", exc)
            # В случае ошибки возвращаем безопасный дефолт.
            return {
                "sentiment": "neutral",
                "categories": [],
                "summary": "",
                "suggestions": "",
            }

        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("AI analyze_review returned non-JSON content: %r", content)
            return {
                "sentiment": "neutral",
                "categories": [],
                "summary": "",
                "suggestions": "",
            }

        sentiment = data.get("sentiment") or "neutral"
        if sentiment not in {"positive", "neutral", "negative"}:
            sentiment = "neutral"

        categories = data.get("categories") or []
        if not isinstance(categories, list):
            categories = []

        summary = data.get("summary") or ""
        if not isinstance(summary, str):
            summary = ""

        suggestions = data.get("suggestions") or ""
        if not isinstance(suggestions, str):
            suggestions = ""

        return {
            "sentiment": sentiment,
            "categories": categories,
            "summary": summary,
            "suggestions": suggestions,
        }

    def analyze_task(self, text: str) -> Dict[str, Any]:
        """
        Анализирует текст задачи (особенно MaintenanceTask).

        Возвращает словарь:
        {
          "problem_type": "plumbing|electricity|noise|cleaning|other",
          "urgency": "low|medium|high|critical",
          "recommendation": "краткое пояснение/что сделать"
        }
        """
        prompt = (
            "Ты — технический ассистент управляющей компании.\n"
            "По тексту задачи определи тип проблемы и рекомендуемую срочность.\n"
            "Ответь строгим JSON без комментариев:\n"
            "{\n"
            '  "problem_type": "plumbing|electricity|noise|cleaning|other",\n'
            '  "urgency": "low|medium|high|critical",\n'
            '  "recommendation": "краткое пояснение/что сделать (по-русски)"\n'
            "}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": text},
                ],
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content or "{}"
        except Exception as exc:  # noqa: BLE001
            logger.exception("AI analyze_task failed: %r", exc)
            return {
                "problem_type": "other",
                "urgency": "medium",
                "recommendation": "",
            }

        import json

        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            logger.warning("AI analyze_task returned non-JSON content: %r", content)
            return {
                "problem_type": "other",
                "urgency": "medium",
                "recommendation": "",
            }

        problem_type = data.get("problem_type") or "other"
        if problem_type not in {"plumbing", "electricity", "noise", "cleaning", "other"}:
            problem_type = "other"

        urgency = data.get("urgency") or "medium"
        if urgency not in {"low", "medium", "high", "critical"}:
            urgency = "medium"

        recommendation = data.get("recommendation") or ""
        if not isinstance(recommendation, str):
            recommendation = ""

        return {
            "problem_type": problem_type,
            "urgency": urgency,
            "recommendation": recommendation,
        }
