from typing import Iterable, List, Set

from django.contrib.auth.models import Group
from rest_framework.permissions import BasePermission

from .models import Staff


def get_user_roles(user) -> Set[str]:
    """
    Возвращает множество ролей пользователя:
    - role из Staff, если профиль существует;
    - имена групп (Group.name), к которым принадлежит пользователь.
    """
    if not user or not user.is_authenticated:
        return set()

    roles: Set[str] = set()

    # Роль из Staff-профиля.
    try:
        staff: Staff = user.staff_profile  # type: ignore[attr-defined]
    except Staff.DoesNotExist:
        staff = None  # type: ignore[assignment]

    if staff is not None and staff.role:
        roles.add(staff.role)

    # Имена групп из Django auth.
    group_names = Group.objects.filter(user=user).values_list("name", flat=True)
    roles.update(group_names)

    return roles


class BaseRolePermission(BasePermission):
    """
    Базовый permission-класс, проверяющий наличие у пользователя нужной роли.

    Наследники должны определить атрибут allowed_roles: Iterable[str].
    """

    allowed_roles: Iterable[str] = ()

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        user_roles = get_user_roles(request.user)
        return bool(set(self.allowed_roles) & user_roles)


class HasAnyRole(BaseRolePermission):
    """
    Пример использования: разрешить доступ для любого из переданных ролей.

    Вьюха может задать свой список ролей:

    class SomeView(...):
        permission_classes = [HasAnyRole]
        required_roles = ["CEO", "COO"]
    """

    def has_permission(self, request, view) -> bool:
        # Если у вьюхи определён required_roles — используем его.
        allowed: Iterable[str] = getattr(view, "required_roles", self.allowed_roles)
        self.allowed_roles = allowed
        return super().has_permission(request, view)


class IsFinanceRole(BaseRolePermission):
    """
    Пример permission-класса для финансовых эндпоинтов.
    """

    allowed_roles: List[str] = ["CEO", "CFO", "Finance"]


class IsCleaningRole(BaseRolePermission):
    """
    Пример permission-класса для задач клининга.
    """

    allowed_roles: List[str] = ["CEO", "COO", "Cleaning"]


class IsMaintenanceRole(BaseRolePermission):
    """
    Пример permission-класса для задач эксплуатации.
    """

    allowed_roles: List[str] = ["CEO", "COO", "Maintenance"]


class IsFinanceSummaryRole(BaseRolePermission):
    """
    Доступ к агрегированному финансовому summary.
    """

    allowed_roles: List[str] = [
        "CEO",
        "COO",
        "CFO",
        "Finance",
        "GM",
        "HotelDirector",
        "Marketing",
    ]


ROLE_ACCESS_MATRIX = {
    # Зона: список ролей, которым по умолчанию разрешён доступ.
    "finance": ["CEO", "CFO", "Finance"],
    "operations_all": ["CEO", "COO"],
    "owners_and_contracts": ["CEO", "CBDO", "Finance"],
    "hotel_management": ["CEO", "COO", "HotelDirector", "GM"],
    "frontdesk": ["CEO", "COO", "HotelDirector", "GM", "FrontDesk"],
    "cleaning": ["CEO", "COO", "Cleaning"],
    "maintenance": ["CEO", "COO", "Maintenance"],
    "quality": ["CEO", "COO", "Quality"],
    "marketing": ["CEO", "COO", "Marketing"],
    "it": ["CEO", "IT"],
}


def user_has_zone_access(user, zone: str) -> bool:
    """
    Проверяет, имеет ли пользователь доступ к зоне по ROLE_ACCESS_MATRIX.
    """
    if not user or not user.is_authenticated:
        return False
    allowed_roles = set(ROLE_ACCESS_MATRIX.get(zone, []))
    if not allowed_roles:
        return False
    return bool(allowed_roles & get_user_roles(user))
