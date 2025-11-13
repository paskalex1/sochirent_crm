from django.conf import settings
from rest_framework.permissions import BasePermission


class LeadCreatePermission(BasePermission):
    """
    Разрешает создание лида если:
    - запрос пришёл с корректным X-API-Key, ИЛИ
    - пользователь аутентифицирован (JWT / сессия).
    """

    def has_permission(self, request, view):
        # Нас интересует только create у LeadViewSet
        if getattr(view, "action", None) != "create":
            return False

        # 1) Проверяем X-API-Key (для RSForm / интеграций)
        api_key = request.headers.get("X-API-Key")
        expected = getattr(settings, "LEAD_API_KEY", None)
        if expected and api_key == expected:
            return True

        # 2) Разрешаем создание аутентифицированным пользователям
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return True

        return False
