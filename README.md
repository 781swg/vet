# AI-менеджер для ветклиники

MVP проекта для небольшой семейной ветеринарной клиники, где врач часто работает без администратора. Система принимает сообщения из клиентских каналов, отвечает по базе услуг, собирает первичную информацию о питомце, сохраняет CRM-историю, создает заявки и передает их врачу в Telegram.

Это не медицинский бот и не замена врачу. AI-помощник отвечает только по услугам, графику, адресу, ветмагазину и сбору данных. Диагнозы, лечение и дозировки запрещены.

## Что уже реализовано

- FastAPI backend.
- PostgreSQL через Docker Compose.
- SQLAlchemy 2.0 async models.
- Alembic migration `0001_initial`.
- Seed-данные для "Ветклиника Дениса".
- Единый формат входящего сообщения.
- Telegram webhook для клиентского бота.
- WhatsApp Cloud API webhook verify, parsing и отправка через Messages API.
- MAX Bot API webhook parsing, проверка `X-Max-Bot-Api-Secret` и отправка через `POST /messages`.
- VK webhook confirmation, parsing и базовая отправка через VK Messages API.
- Dialog Manager с сохранением контактов, диалогов и сообщений.
- LLM Agent с OpenAI-compatible клиентом и безопасным эвристическим fallback.
- Emergency detection и handoff врачу.
- Intake form и lead creation.
- Telegram-бот врача на aiogram.
- Команды врача `/today`, `/week`, `/month`, `/leads`, `/help`.
- Inline-кнопки для смены статуса заявки.
- Отчеты из PostgreSQL-данных.
- Redis/RQ очередь: webhook быстро отвечает, LLM-обработка идет в worker.
- Idempotency для webhook updates через таблицу `webhook_events`.
- Rate limiting входящих webhook endpoints.
- Admin API закрыт ключом `X-Admin-API-Key`.
- Скрипт настройки реальных Telegram/MAX webhook URLs.
- Whitelisted SQL tool layer для LLM-контекста: услуги, знания, правила, возможности врача.
- Lightweight embeddings helper для knowledge chunks.
- Backup/restore scripts для PostgreSQL.
- `/ready` и `/metrics` для мониторинга.
- Базовые pytest-тесты.

## Архитектура

```text
Telegram / WhatsApp / MAX / VK
        ↓
Channel Adapter
        ↓
Unified Message Gateway
        ↓
Dialog Manager
        ↓
Intent Classifier
        ↓
CRM / SQL / Knowledge Base Search
        ↓
LLM Agent
        ↓
Response Safety Validator
        ↓
Channel Sender
        ↓
Клиент

Dialog Manager
        ↓
Lead / Intake Form / Client Profile
        ↓
Doctor Telegram Bot
        ↓
Врач
```

## Запуск

1. Создайте `.env`:

```bash
cp .env.example .env
```

2. Заполните токены:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/vet_ai_manager
DEFAULT_BUSINESS_ID=1
TELEGRAM_CLIENT_BOT_TOKEN=...
TELEGRAM_DOCTOR_BOT_TOKEN=...
TELEGRAM_CLIENT_BOT_USERNAME=denisclinik_bot
TELEGRAM_DOCTOR_BOT_USERNAME=Denis_Notification_klinila_bot
DOCTOR_TELEGRAM_USER_ID=123456789
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
WHATSAPP_ACCESS_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_VERIFY_TOKEN=
WHATSAPP_API_VERSION=v21.0
WHATSAPP_WEBHOOK_SECRET=
MAX_BOT_TOKEN=
MAX_WEBHOOK_SECRET=
MAX_API_BASE_URL=https://platform-api.max.ru
VK_ACCESS_TOKEN=
VK_CONFIRMATION_TOKEN=
VK_SECRET=
PUBLIC_BASE_URL=https://your-domain.com
ADMIN_API_KEY=change-me
REDIS_URL=redis://redis:6379/0
QUEUE_ENABLED=true
QUEUE_NAME=webhooks
WEBHOOK_RATE_LIMIT_PER_MINUTE=120
TOKEN_ENCRYPTION_KEY=
BACKUP_DIR=/app/backups
```

3. Запустите:

```bash
docker compose up --build
```

API будет доступен на `http://localhost:8000`.

Сайт клиники теперь находится внутри этого же проекта в папке `site/` и отдается тем же FastAPI-приложением:

```text
http://localhost:8000/
```

Форма на сайте отправляет заявку в:

```text
POST /api/site/leads
```

Эта ручка создает в PostgreSQL контакт, диалог, сообщение, intake form, lead, analytics events и отправляет врачу уведомление через `TELEGRAM_DOCTOR_BOT_TOKEN`.

Клиентская ссылка для заявок:

```text
https://t.me/denisclinik_bot
```

Внутренний бот уведомлений врача:

```text
@Denis_Notification_klinila_bot
```

Важно: username бота не заменяет токен. Для реальной отправки сообщений нужны `TELEGRAM_CLIENT_BOT_TOKEN`, `TELEGRAM_DOCTOR_BOT_TOKEN` и числовой `DOCTOR_TELEGRAM_USER_ID`.

Worker очереди запускается отдельным сервисом `worker`, Redis — отдельным сервисом `redis`. Webhook endpoints регистрируют событие, кладут задачу в очередь и возвращают `200 OK`; ответ клиенту отправляет worker.

PostgreSQL хранит данные внутри папки проекта: `data/postgres`. Это bind-mount из `docker-compose.yml`, поэтому базу можно найти, архивировать или перенести вместе с проектом. Саму папку с файлами PostgreSQL не нужно коммитить.

Для просмотра таблиц в браузере в Compose добавлен Adminer:

```text
http://localhost:8080
```

Параметры входа: system `PostgreSQL`, server `db`, user `postgres`, password `postgres`, database `vet_ai_manager`.

## Admin API

Все endpoints `/api/admin/*` требуют заголовок:

```text
X-Admin-API-Key: значение_из_ADMIN_API_KEY
```

Пример:

```bash
curl http://localhost:8000/api/admin/leads \
  -H 'X-Admin-API-Key: change-me-local-admin-key'
```

Токены каналов не нужно хранить открытым текстом. Можно сохранить внешний reference:

```bash
curl -X PATCH http://localhost:8000/api/admin/channels/token \
  -H 'X-Admin-API-Key: change-me-local-admin-key' \
  -H 'Content-Type: application/json' \
  -d '{"channel_type":"whatsapp","token_ref":"secret-manager://whatsapp/access-token"}'
```

Если нужен encrypted token в базе, задайте `TOKEN_ENCRYPTION_KEY` Fernet-ключом и отправьте поле `token`.

## Telegram

Клиентский бот принимает webhook:

```text
POST /api/webhooks/telegram
```

Для локальной проверки можно отправить payload вручную:

```bash
curl -X POST http://localhost:8000/api/webhooks/telegram \
  -H 'Content-Type: application/json' \
  -d '{"message":{"date":1710000000,"text":"Здравствуйте, вы лечите кроликов?","from":{"id":10,"first_name":"Анна"},"chat":{"id":10}}}'
```

Врачебный бот запускается отдельным сервисом `doctor-bot`. Он получает новые заявки, показывает отчеты и меняет статусы lead через inline-кнопки.

Настройка реального Telegram webhook:

```bash
PUBLIC_BASE_URL=https://your-domain.com python scripts/setup_webhooks.py
```

Токен все равно создается в BotFather вручную, а скрипт вызывает Telegram Bot API `setWebhook`.

## WhatsApp

WhatsApp подключается как канал общей системы, не как отдельный проект:

```text
WhatsApp Cloud API → /api/webhooks/whatsapp → WhatsAppAdapter → DialogManager → WhatsAppAdapter.send_text()
```

Нужные переменные:

```env
WHATSAPP_ACCESS_TOKEN=...
WHATSAPP_PHONE_NUMBER_ID=...
WHATSAPP_VERIFY_TOKEN=...
WHATSAPP_API_VERSION=v21.0
WHATSAPP_WEBHOOK_SECRET=
```

Meta проверяет webhook через:

```text
GET /api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=...&hub.challenge=...
```

Входящие `text`-сообщения из payload Meta превращаются в `UnifiedIncomingMessage`, проходят общий `DialogManager`, сохраняются в единой PostgreSQL-базе и получают ответ через WhatsApp Messages API.

## MAX

MAX также подключен как канал:

```text
MAX Bot API → /api/webhooks/max → MaxAdapter → DialogManager → MaxAdapter.send_text()
```

Нужные переменные:

```env
MAX_BOT_TOKEN=...
MAX_WEBHOOK_SECRET=...
MAX_API_BASE_URL=https://platform-api.max.ru
```

Если `MAX_WEBHOOK_SECRET` задан, endpoint проверяет заголовок `X-Max-Bot-Api-Secret`. Адаптер принимает события `message_created`, достает `user_id`, `chat_id`, `text`, сохраняет сообщение и отправляет ответ через `POST /messages`.

## VK

VK оставлен в той же архитектуре каналов:

```text
VK Callback API → /api/webhooks/vk → VkAdapter → DialogManager → VkAdapter.send_text()
```

Endpoint поддерживает `confirmation` и возвращает `VK_CONFIRMATION_TOKEN`. Для сообщений используется тип `message_new`.

## HTTPS callback URLs

Для production укажите:

```env
PUBLIC_BASE_URL=https://your-domain.com
```

Затем выполните:

```bash
python scripts/setup_webhooks.py
```

Скрипт программно настраивает Telegram `setWebhook` и MAX subscription. WhatsApp и VK выводятся как callback URLs, которые нужно внести в кабинеты Meta/VK:

```text
https://your-domain.com/api/webhooks/whatsapp
https://your-domain.com/api/webhooks/vk
```

## API

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `POST /api/webhooks/telegram`
- `GET /api/webhooks/whatsapp`
- `POST /api/webhooks/whatsapp`
- `POST /api/webhooks/max`
- `POST /api/webhooks/vk`
- `POST /api/admin/services`
- `GET /api/admin/services`
- `POST /api/admin/prices`
- `GET /api/admin/prices`
- `GET /api/admin/leads`
- `GET /api/admin/leads/{id}`
- `PATCH /api/admin/leads/{id}/status`
- `GET /api/admin/reports/daily`
- `GET /api/admin/reports/weekly`
- `GET /api/admin/reports/monthly`
- `GET /api/admin/channels`
- `PATCH /api/admin/channels/token`

## LLM

`app/llm/client.py` ходит в OpenAI-compatible API:

```env
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=...
OPENAI_MODEL=gpt-4o-mini
```

Если ключи не заданы, работает безопасный fallback: эвристическое определение intent, поиск услуг в базе, сбор заявки и emergency-проверка.

LLM получает SQL-контекст через `SQLToolbox`, а не через произвольный SQL. Разрешенные инструменты: поиск услуги, поиск knowledge chunks, правила бизнеса и возможности врача. Это закрывает опасный сценарий “модель сама пишет SQL”.

## Медицинская безопасность

Бот не должен:

- ставить диагнозы;
- назначать лечение;
- рекомендовать дозировки;
- обещать выздоровление;
- заменять врача.

При признаках срочности бот отвечает коротко, советует срочно звонить врачу или ехать в круглосуточную клинику, создает lead и handoff с высоким приоритетом.

## База данных

Основные таблицы:

- `businesses`, `channels`;
- `contacts`, `contact_channel_accounts`, `animals`;
- `conversations`, `messages`;
- `services`, `animal_types`, `prices`, `doctor_capabilities`;
- `intake_forms`, `leads`, `appointments`, `handoff_tasks`;
- `analytics_events`, `report_snapshots`, `audit_logs`;
- `webhook_events`;
- `knowledge_sources`, `knowledge_chunks`, `business_rules`, `prompt_configs`.

Seed-данные создаются командой:

```bash
python scripts/seed.py
```

В Docker Compose seed запускается автоматически после миграций.

Физические файлы PostgreSQL при запуске Docker Compose будут в:

```text
data/postgres
```

## Очередь, idempotency и rate limiting

Входящие webhook-и проходят так:

```text
Webhook → parse adapter → webhook_events unique key → Redis/RQ job → worker → DialogManager → ответ в канал
```

Если платформа повторно доставит один и тот же update, `webhook_events` не даст обработать его второй раз. Rate limit настраивается через `WEBHOOK_RATE_LIMIT_PER_MINUTE`.

## Backup и restore

Создать backup:

```bash
scripts/backup_postgres.sh
```

Файлы будут лежать в `backups/`. Восстановить:

```bash
scripts/restore_postgres.sh backups/vet_ai_manager_YYYYmmdd_HHMMSS.dump
```

Retention задается `BACKUP_RETENTION_DAYS`.

## Мониторинг

- `GET /ready` проверяет PostgreSQL и Redis.
- `GET /metrics` отдает Prometheus-метрики.

## Отчеты

Врач может запросить:

- `/today` — отчет за день;
- `/week` — отчет за текущую неделю;
- `/month` — отчет за текущий месяц;
- `/leads` — последние заявки.

Метрики считаются из сообщений, контактов, заявок, intake forms, appointments и handoff tasks.

## Тесты

```bash
python -m pytest
```

Покрыто:

- normalizer;
- intent detection;
- emergency detection;
- safety validator;
- service search;
- lead creation;
- report generation.
- WhatsApp adapter parsing;
- MAX adapter parsing.
- webhook idempotency.

## Что еще доделать для production

- Уточнить юридические тексты согласия на обработку персональных данных.
- Подключить настоящий secret manager вместо локальных `.env` refs.
- Добавить полноценный Prometheus/Grafana stack и alerting.
- Заменить lightweight embeddings на embeddings provider и vector index, когда появится объемная база знаний.
