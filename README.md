# Feed Aggregator — Агрегатор фидов объектов новостроек

Приложение-прослойка для АН МИЭЛЬ Барнаул: объединяет XML-фиды и Excel-таблицы
от нескольких застройщиков в единый XML-фид для CRM Intrum.

## Архитектура

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│ Яндекс XML  │  │ Авито XML   │  │ ЦИАН XML    │  ... Excel/CSV
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │
       └────────────────┼────────────────┘
                        ▼
              ┌─────────────────┐
              │  Парсеры (5 шт) │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Нормализатор   │
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Идентификатор  │  ← Стабильный ExternalId
              │  + Дедупликация │    4-шаговый алгоритм
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  Генератор XML  │  → feed.xml (ЦИАН Feed v2)
              └────────┬────────┘
                       ▼
              ┌─────────────────┐
              │  CRM Intrum     │  ← Забирает по URL
              └─────────────────┘
```

## Стек технологий

- **Backend**: Python 3.11+, FastAPI, SQLAlchemy (async), APScheduler
- **Frontend**: React 18, Tailwind CSS, Recharts, Vite
- **Database**: PostgreSQL 16
- **Parsers**: lxml (XML), openpyxl + pandas (Excel/CSV)
- **Notifications**: Telegram Bot API
- **Deploy**: Docker + docker-compose, Nginx

## Быстрый старт

### 1. Клонировать и настроить

```bash
cp .env.example .env
# Отредактировать .env: задать пароли, Telegram-токен и т.д.
```

### 2. Запуск через Docker

```bash
docker-compose up -d --build
```

Сервисы:
- **API + Admin**: http://localhost:8000
- **Feed XML**: http://localhost:8080/feed/feed.xml
- **PostgreSQL**: localhost:5432

### 3. Первый вход

Логин: `admin` / пароль из `.env` (ADMIN_PASSWORD).

### 4. Добавить источник

В админ-панели → Источники → Добавить:
- Выбрать тип (Яндекс, Авито, ЦИАН, Произвольный XML, Excel)
- Указать URL фида
- Нажать "Тест" для проверки

### 5. Запуск синхронизации

- **Автоматически**: каждые 4 часа (настраивается SYNC_INTERVAL_HOURS)
- **Вручную**: Админ-панель → Выходной фид → «Запустить синхронизацию»

## Структура проекта

```
feed-aggregator/
├── app/
│   ├── main.py              # FastAPI приложение
│   ├── config.py             # Настройки из .env
│   ├── database.py           # Подключение к БД
│   ├── models/               # SQLAlchemy модели
│   ├── parsers/              # 5 парсеров (yandex, avito, cian, custom_xml, excel)
│   ├── normalizer/           # Нормализация данных
│   ├── identifier/           # Идентификация + дедупликация
│   ├── generator/            # Генерация XML-фида
│   ├── monitoring/           # Telegram-уведомления
│   ├── scheduler/            # Планировщик + оркестратор синхронизации
│   ├── api/                  # REST API эндпоинты
│   └── schemas/              # Pydantic-схемы
├── frontend/                 # React админ-панель
├── alembic/                  # Миграции БД
├── tests/                    # Тесты
├── nginx/                    # Конфигурация Nginx
├── docker-compose.yml
├── Dockerfile
└── requirements.txt
```

## API эндпоинты

| Метод | URL | Описание |
|-------|-----|----------|
| POST | /api/auth/login | Авторизация (JWT) |
| GET | /api/dashboard | Статистика и здоровье системы |
| GET/POST | /api/sources | CRUD источников |
| POST | /api/sources/{id}/test | Тест-загрузка источника |
| GET | /api/objects | Поиск и фильтрация объектов |
| GET | /api/objects/{id}/history | История изменений объекта |
| GET | /api/logs | Журнал синхронизаций |
| GET/POST | /api/mappings | Управление маппингами |
| POST | /api/feed/sync | Ручной запуск синхронизации |
| GET | /api/feed/download | Скачать XML-фид |
| GET | /api/notifications/alerts | История уведомлений |

## Форматы входных данных

| Формат | Тип | Ключевые теги |
|--------|-----|---------------|
| Яндекс.Недвижимость | yandex | `<realty-feed>` → `<offer>` |
| Авито Autoload | avito | `<Ads>` → `<Ad>` |
| ЦИАН Feed v2 | cian | `<Feed>` → `<Object>` + `<JKSchema>` |
| Произвольный XML | custom_xml | Настраиваемый XPath-маппинг |
| Excel/CSV | excel | Настраиваемый маппинг столбцов |

## Алгоритм идентификации (ExternalId)

1. **Точное совпадение**: source_id + jk_name + house_name + flat_number
2. **Нечёткое** (перенумерация): тот же источник + этаж + площадь ±0.5 + комнаты
3. **Расхождение**: несколько кандидатов или площадь > 2 м² — новый объект
4. **Новый объект**: создание с ExternalId `{DEV_CODE}-{JK_CODE}-{SEQ}`

## Обработка удалённых объектов

- 1-й пропуск: missing_count = 1, остаётся в фиде
- 2-й пропуск (через 4ч): missing_count = 2, остаётся
- 3-й пропуск (через 8ч): status = removed, удалён из фида

## Telegram-уведомления

| Событие | Уровень |
|---------|---------|
| Источник недоступен | CRITICAL |
| 0 объектов | CRITICAL |
| Падение > 20% | WARNING |
| Массовое изменение цен | WARNING |
| Перенумерация квартир | INFO |
| Успешная синхронизация | INFO |

## Запуск тестов

```bash
pytest tests/ -v --cov=app
```

## Frontend (разработка)

```bash
cd frontend
npm install
npm run dev    # http://localhost:3000
npm run build  # Сборка в static/admin/
```

## Переменные окружения

См. `.env.example` для полного списка. Ключевые:

- `DATABASE_URL` — подключение к PostgreSQL
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` — Telegram-уведомления
- `SYNC_INTERVAL_HOURS` — интервал синхронизации (по умолчанию 4)
- `THRESHOLD_DROP_WARNING` — порог падения объектов (%) для WARNING
- `THRESHOLD_DROP_CRITICAL` — порог для CRITICAL (фид не обновляется)

## Лицензия

Proprietary — АН МИЭЛЬ Барнаул (ml22.ru)
