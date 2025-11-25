# Roles and Permissions (Sochi.Rent CRM)

Этот документ описывает, как устроена система ролей и прав доступа в CRM.

## 1. Модель Staff и связи с пользователем

- Модель: `apps.staff.models.Staff`
  - `user` — OneToOneField на `AUTH_USER_MODEL` (Django User).
  - `full_name`, `position`, `department`, `phone`, `email`.
  - `role` — бизнес‑роль сотрудника (см. ниже).
  - `properties` — ManyToMany к `Property` (какие объекты закреплены за сотрудником, напр. GM).

- При сохранении `Staff.save()`:
  - Определяется предыдущая роль (`old_role`).
  - Пользователь удаляется из группы `old_role` (если изменилась).
  - Пользователь добавляется в Django Group с именем новой роли (`self.role`), создаётся при необходимости.

Таким образом, права можно настраивать:
- либо через `Staff.role`,
- либо напрямую через группы/permissions в админке (Django auth).

## 2. Перечень ролей (Staff.Role)

Определены в `apps.staff.models.Staff.Role`:

- `CEO`
- `COO`
- `PROPERTY_MANAGER` (`"PropertyManager"`)
- `CFO`
- `CBDO`
- `HOTEL_DIRECTOR` (`"HotelDirector"`)
- `GM` (`"GM"`, General Manager)
- `FRONT_DESK` (`"FrontDesk"`)
- `CLEANING`
- `MAINTENANCE`
- `QUALITY`
- `MARKETING`
- `FINANCE`
- `IT`
- `HR`

Подразделения (`Staff.Department`) используются только как справочник (не влияют напрямую на права).

## 3. Permission‑классы (DRF)

Реализованы в `apps.staff/permissions.py`.

### Базовый слой

- `get_user_roles(user) -> set[str]`
  - Собирает:
    - `Staff.role` (если профиль существует),
    - имена Django Groups, в которых состоит пользователь.

- `BaseRolePermission`
  - Базовый DRF‑permission.
  - Наследники задают `allowed_roles: Iterable[str]`.
  - Доступ разрешён, если пересечение `allowed_roles` и реальных ролей пользователя не пусто.

- `HasAnyRole`
  - Вьюха может задать список ролей в `required_roles`.
  - Пример:
    ```python
    class SomeView(APIView):
        permission_classes = [HasAnyRole]
        required_roles = ["CEO", "COO"]
    ```

### Специализированные permissions

- `IsFinanceRole`
  - `allowed_roles = ["CEO", "CFO", "Finance"]`
  - Используется для финансовых viewset’ов:
    - `/api/v1/finance-records/`
    - `/api/v1/expenses/`
    - `/api/v1/payouts/`
    - `/api/v1/owner-reports/`

- `IsFinanceSummaryRole`
  - `allowed_roles = ["CEO", "COO", "CFO", "Finance", "GM", "HotelDirector", "Marketing"]`
  - Доступ к агрегированному `FinanceSummaryView` (без детализации операций).

- `IsCleaningRole`
  - `allowed_roles = ["CEO", "COO", "Cleaning"]`

- `IsMaintenanceRole`
  - `allowed_roles = ["CEO", "COO", "Maintenance"]`

- `IsPropertyManagerDashboardRole`
  - `allowed_roles = ["CEO", "COO", "PropertyManager"]`
  - Для `PropertyManagerDashboardView`.

- `IsAIRole`
  - `allowed_roles = ["CEO", "COO", "PropertyManager", "GM", "Maintenance", "Quality"]`
  - Для AI‑эндпоинтов:
    - `/api/v1/ai/reviews/analyze/`
    - `/api/v1/ai/tasks/maintenance/{id}/analyze/`

- `IsRevenueRole`
  - `allowed_roles = ["CEO", "COO", "PropertyManager", "GM"]`
  - Для Revenue‑эндпоинтов:
    - `/api/v1/revenue/price-suggestion/`
    - `/api/v1/revenue/price-recommendations/`

## 4. Фильтрация данных по ролям (get_queryset)

Помимо явных permissions, многие viewset’ы ограничивают данные в `get_queryset()` в зависимости от `Staff.role`.

Примеры:

### Properties / Units / Bookings

- В `apps/properties/api.py::PropertyViewSet.get_queryset()`:
  - Неаутентифицированный пользователь → видит базовый список (ограничения доступа реализуются на фронте/через другие слои).
  - `GM` → только объекты, закреплённые за ним через `Staff.properties`.
  - `HotelDirector` → только объекты `Property` с типом `hotel`.

- В `UnitViewSet.get_queryset()`:
  - `GM` → только юниты по своим объектам.
  - `HotelDirector` → юниты объектов типа `hotel`.

- В `apps/bookings/api.py::BookingViewSet.get_queryset()`:
  - `GM` → только бронирования по своим объектам.
  - `HotelDirector` → бронирования только по hotel‑объектам.
  - `FrontDesk` → только бронирования по своим объектам.

- В `GuestViewSet.get_queryset()`:
  - `GM`, `FrontDesk` → только гости, которые бронировали их объекты.
  - `HotelDirector` → гости по объектам типа `hotel`.

### Tasks (operations)

В `apps/operations/api.py`:

- `BaseTaskViewSet.get_queryset()`:
  - `GM` → только задачи по своим объектам.
  - `HotelDirector` → только задачи по объектам‑отелям.

- `CleaningTaskViewSet.get_queryset()`:
  - `Cleaning` → только задачи, где пользователь указан исполнителем.

- `CheckinTaskViewSet.get_queryset()`:
  - `FrontDesk` → только check‑in задачи по своим объектам.

- `CheckoutTaskViewSet.get_queryset()`:
  - `FrontDesk` → только check‑out задачи по своим объектам.

- `QualityInspectionTaskViewSet.get_queryset()`:
  - `Quality` → все задачи контроля качества (с учётом ограничений базового viewset’а).

### Dashboards

- `GMDashboardView`:
  - Требует роль `GM`.
  - Показывает только отели (`Property` с типом `hotel`), закреплённые за этим GM.

- `PropertyManagerDashboardView`:
  - Для ролей: CEO, COO, PropertyManager.
  - CEO/COO видят все объекты, PropertyManager — только закреплённые.

### Owner Extranet

- Для эндпоинтов:
  - `/api/v1/extranet/owner/dashboard/`
  - `/api/v1/extranet/owner/reports/`

Проверка делается через `request.user.owner_profile` (модель `Owner` связана с `User` полем `user`).  
Таким образом:

- только пользователи, связанные с `Owner`, могут видеть свои объекты и отчёты;
- данные фильтруются по `owner` на уровне queryset.

## 5. Практические рекомендации

- Для нового сотрудника:
  1. Создать Django User (email/логин).
  2. Создать `Staff`, связать с User, задать `role` и при необходимости список `properties`.
  3. При сохранении `Staff` пользователь автоматически попадёт в нужную Django Group.

- Для нового API‑эндпоинта:
  - Если это:
    - финансовый сервис → использовать `IsFinanceRole` или `IsFinanceSummaryRole`;
    - операционные таски → `IsCleaningRole`, `IsMaintenanceRole` и т.п.;
    - AI/Revenue → `IsAIRole` / `IsRevenueRole`;
  - и при необходимости добавить дополнительную фильтрацию в `get_queryset()` по `Staff.role`.

