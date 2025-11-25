# Changelog

## Sprint — Owner Extranet, AI‑анализ и Revenue Management

- **F3 — Owner Extranet**
  - Реализован кабинет собственника:
    - `GET /api/v1/extranet/owner/dashboard/` — сводка по объектам, занятости, агрегированным доходам/расходам/прибыли и крупным задачам Maintenance за период.
    - `GET /api/v1/extranet/owner/reports/?year=&month=` — список `OwnerReport` только для текущего авторизованного собственника.
  - Добавлена связь `Owner ↔ User` (`owner_profile`) и ограничение доступа к данным только своими объектами.

- **G2 — AI‑модуль (анализ отзывов и задач)**
  - Добавлен сервис `AIClient` (OpenAI Chat Completions) с методами:
    - `analyze_review(text)` — определяет тональность, категории проблем, summary и рекомендации по работе с гостем.
    - `analyze_task(text)` — классифицирует тип проблемы, рекомендуемую срочность и даёт текстовую рекомендацию.
  - Новая модель `ReviewAnalysis` и эндпоинт:
    - `POST /api/v1/ai/reviews/analyze/` — анализ текста отзыва и создание `ReviewAnalysis`, связанной с booking/property/unit.
  - Расширен `MaintenanceTask` AI‑полями:
    - `ai_problem_type`, `ai_urgency`, `ai_recommendation`, `ai_last_analyzed_at`.
    - Эндпоинт `POST /api/v1/ai/tasks/maintenance/{id}/analyze/` заполняет эти поля по `title + description`.
  - Доступ к AI‑эндпоинтам ограничен ролями: CEO, COO, PropertyManager, GM, Maintenance, Quality.

- **G3 — Динамическое ценообразование (Revenue Management, базовый уровень)**
  - Новое приложение `apps.revenue` и модель `PriceRecommendation` для логирования рекомендованных цен по юниту и дате.
  - Сервис `suggest_price_for_unit_on_date(unit, date)`:
    - использует `RatePlan.base_price`, загрузку по объекту за 7 и 30 дней и сезонность (low / shoulder / high);
    - применяет набор простых коэффициентов (наценки/скидки) и ограничивает итоговую цену диапазоном `[0.7 × base; 1.5 × base]`;
    - формирует человеко‑читабельное объяснение `notes` (база, загрузка, сезон, обрезка по min/max, итоговая цена).
  - Эндпоинты:
    - `GET /api/v1/revenue/price-suggestion/?unit_id=&date=` — рассчитывает и логирует рекомендованную цену.
    - `GET /api/v1/revenue/price-recommendations/?unit_id=&date_from=&date_to=` — возвращает историю рекомендаций для выбранного юнита.
  - Доступ к Revenue‑эндпоинтам ограничен ролями: CEO, COO, PropertyManager, GM.

