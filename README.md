# Sochi.Rent CRM Core

Backend‑ядро CRM‑системы Sochi.Rent на Django для управления объектами недвижимости, бронированиями, операционными задачами, финансами и отчетностью собственникам.  
Основные сценарии: property / hotel management, кабинет собственника (Owner Extranet), базовый AI‑анализ и модуль динамического ценообразования.

## Основные возможности

- **Объекты и юниты**
  - Модели `Property` (residential_short / residential_long / commercial / hotel) и `Unit`.
  - Связь с `Owner`, ответственный менеджер, статусы и ключевые характеристики.
  - Карточки объекта и юнита с агрегированными показателями и календарём занятости.

- **Бронирования и гости**
  - Модели `Guest`, `Booking`, `RatePlan`, `CalendarEvent`.
  - Поддержка статусов брони и источников (OTA, прямые, корпоративные, долгосрочные).
  - Карточка брони с задачами, финансовыми записями и историей статусов.

- **Операционные задачи**
  - Базовый класс `TaskBaseModel` и специализированные задачи:
    - `CleaningTask`, `MaintenanceTask`, `CheckinTask`, `CheckoutTask`,
    - `QualityInspectionTask`, `OwnerRequestTask`.
  - Фильтрация по типу задачи, статусу, исполнителю, объекту.
  - SLA‑отчёт по задачам эксплуатации.

- **Финансовый контур**
  - Модели `FinanceRecord`, `Expense`, `Payout`, `OwnerReport`.
  - Генерация ежемесячных отчётов собственнику с разбивкой по объектам и крупным задачам.
  - Агрегированное финансовое summary для управленческих и маркетинговых ролей.

- **Сотрудники и роли**
  - Модель `Staff` с ролями (CEO, COO, CFO, PropertyManager, GM, FrontDesk, Cleaning, Maintenance, Quality и др.).
  - Автоматическая синхронизация ролей с Django Groups.
  - Permission‑классы и фильтрация queryset’ов в зависимости от оргструктуры (подробно — в `docs/ROLES.md`).

- **Панели и кабинеты**
  - GM Dashboard по отелям (`/api/v1/gm-dashboard/`).
  - Property Manager Dashboard (`/api/v1/property-manager/dashboard/`).
  - **Owner Extranet**:
    - `/api/v1/extranet/owner/dashboard/` — сводка по объектам собственника (занятость, агрегированная экономика, ключевые задачи).
    - `/api/v1/extranet/owner/reports/` — список `OwnerReport` для текущего авторизованного собственника.

- **AI‑модуль (G2)**
  - Приложения `apps.ai` и `apps.reviews`:
    - Модель `ReviewAnalysis` — хранение результатов анализа отзывов и жалоб гостей.
    - Сервис `AIClient` (`apps/ai/services.py`), использующий OpenAI Chat Completions.
  - Эндпоинты:
    - `POST /api/v1/ai/reviews/analyze/` — анализ текста отзыва и создание `ReviewAnalysis`.
    - `POST /api/v1/ai/tasks/maintenance/{id}/analyze/` — AI‑классификация `MaintenanceTask` (тип проблемы, срочность, рекомендация).
  - Результаты анализа задач сохраняются в поля `ai_problem_type`, `ai_urgency`, `ai_recommendation`, `ai_last_analyzed_at` и доступны в `/api/v1/tasks/maintenance/` (только для чтения).

- **Динамическое ценообразование (G3)**
  - Приложение `apps.revenue`:
    - Модель `PriceRecommendation` — история рекомендованных цен по юниту и дате.
    - Сервис `suggest_price_for_unit_on_date(unit, date)`:
      - Берёт `base_price` из активного `RatePlan` объекта.
      - Считает загрузку за последние 7 и 30 дней.
      - Определяет сезон (low / shoulder / high).
      - Применяет набор простых коэффициентов и ограничивает итоговую цену диапазоном `[0.7 × base; 1.5 × base]`.
      - Формирует человеко‑читабельное пояснение `notes` на русском.
  - Эндпоинты:
    - `GET /api/v1/revenue/price-suggestion/?unit_id=&date=YYYY-MM-DD`  
      → возвращает рекомендованную цену и создаёт запись в `PriceRecommendation`.
    - `GET /api/v1/revenue/price-recommendations/?unit_id=&date_from=&date_to=`  
      → возвращает историю рекомендаций для юнита за выбранный период.

## Технологии

- Python 3.11+
- Django 5.x
- Django REST Framework
- django-filter
- django-environ
- openai (Chat Completions API)
- SQLite (по умолчанию) или PostgreSQL через настройки окружения.

## Установка и запуск

1. **Клонирование репозитория**

```bash
git clone git@github.com:.../sochirent_core.git
cd sochirent_core
```

2. **Виртуальное окружение и зависимости**

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

3. **Настройка окружения**

Создай `.env` в корне проекта:

```env
DEBUG=True

# База (опционально, если используешь Postgres)
# DB_NAME=sochirent
# DB_USER=...
# DB_PASSWORD=...
# DB_HOST=127.0.0.1
# DB_PORT=5432

LEAD_API_KEY=...

# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL_NAME=gpt-5.1
```

Если переменные БД не заданы, используется SQLite (`db.sqlite3`).

4. **Миграции**

```bash
python manage.py migrate
```

5. **Создание суперпользователя**

```bash
python manage.py createsuperuser
```

6. **Запуск сервера**

```bash
python manage.py runserver
```

- Админка: `http://127.0.0.1:8000/admin/`
- CRM‑дашборд: `/`
- API: `http://127.0.0.1:8000/api/v1/...`

## Ключевые API‑эндпоинты (кратко)

Основные viewset’ы зарегистрированы в `config/urls.py` через `DefaultRouter`:

- `/api/v1/owners/`
- `/api/v1/properties/`, `/api/v1/units/`
- `/api/v1/guests/`, `/api/v1/bookings/`, `/api/v1/rate-plans/`
- `/api/v1/tasks/cleaning/`, `/api/v1/tasks/maintenance/`, `/api/v1/tasks/checkin/`, `/api/v1/tasks/checkout/`, `/api/v1/tasks/quality-inspection/`, `/api/v1/tasks/owner-request/`
- `/api/v1/finance-records/`, `/api/v1/expenses/`, `/api/v1/payouts/`, `/api/v1/owner-reports/`

Специальные эндпоинты:

- GM dashboard: `/api/v1/gm-dashboard/`
- Property Manager dashboard: `/api/v1/property-manager/dashboard/`
- Финансовое summary: `/api/v1/finance-summary/`
- SLA по Maintenance: `/api/v1/maintenance-sla/`
- Owner Extranet:
  - `/api/v1/extranet/owner/dashboard/`
  - `/api/v1/extranet/owner/reports/`
- AI:
  - `POST /api/v1/ai/reviews/analyze/`
  - `POST /api/v1/ai/tasks/maintenance/{id}/analyze/`
- Revenue:
  - `GET /api/v1/revenue/price-suggestion/`
  - `GET /api/v1/revenue/price-recommendations/`

## Примеры запросов (curl)

Ниже — примеры для локального запуска.  
Способ авторизации (BasicAuth, сессии, токены) может отличаться в зависимости от конфигурации; в примерах используется базовая авторизация.

### Owner Extranet

**Дашборд собственника**

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/extranet/owner/dashboard/?year=2025&month=7" \
  -H "Accept: application/json" \
  -u admin:password
```

**Список отчётов собственника**

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/extranet/owner/reports/?year=2025" \
  -H "Accept: application/json" \
  -u admin:password
```

### AI‑анализ отзывов и задач

**Анализ отзыва гостя**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/ai/reviews/analyze/" \
  -H "Content-Type: application/json" \
  -u admin:password \
  -d '{
    "booking_id": 123,
    "source": "manual",
    "text": "В номере было шумно, уборка mediocre, но персонал вежливый."
  }'
```

**AI‑анализ задачи MaintenanceTask**

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/ai/tasks/maintenance/42/analyze/" \
  -H "Accept: application/json" \
  -u admin:password
```

### Revenue Management

**Получить рекомендованную цену для юнита**

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/revenue/price-suggestion/?unit_id=10&date=2025-07-15" \
  -H "Accept: application/json" \
  -u admin:password
```

**История рекомендаций по юниту за период**

```bash
curl -X GET "http://127.0.0.1:8000/api/v1/revenue/price-recommendations/?unit_id=10&date_from=2025-07-01&date_to=2025-07-31" \
  -H "Accept: application/json" \
  -u admin:password
```

## Роли и права доступа

Подробное описание ролей, групп и permission‑классов — в `docs/ROLES.md`.  
Кратко:

- `Staff.role` определяет бизнес‑роль пользователя (CEO, COO, GM и другие).
- При сохранении `Staff` пользователь автоматически добавляется в Django Group с тем же именем.
- Permission‑классы в `apps/staff/permissions.py` используют роли/группы для ограничения доступа к API и фильтрации данных.
