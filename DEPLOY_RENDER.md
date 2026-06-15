# Деплой проекта на Render бесплатно

Этот пакет уже очищен для деплоя: внутри один FastAPI-сервис, который отдает сайт, принимает заявки с сайта и принимает webhook от двух Telegram-ботов.

## Что нужно заранее

1. GitHub-репозиторий с содержимым этой папки.
2. Бесплатная Postgres база. Лучше Neon Free или Supabase Free. Render Postgres Free не подходит для постоянной работы, потому что живет 30 дней.
3. Токены двух Telegram-ботов из BotFather.
4. Числовой `DOCTOR_TELEGRAM_USER_ID` врача.

## Переменные окружения в Render

Обязательные:

```env
DATABASE_URL=postgresql+asyncpg://...
PUBLIC_BASE_URL=https://your-service-name.onrender.com
TELEGRAM_CLIENT_BOT_TOKEN=...
TELEGRAM_DOCTOR_BOT_TOKEN=...
DOCTOR_TELEGRAM_USER_ID=123456789
QUEUE_ENABLED=false
APP_ENV=production
```

Опциональные:

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4o-mini
```

Если OpenAI-переменные пустые, проект должен работать в fallback-режиме без LLM.

## Создание сервиса

Вариант A, через Blueprint:

1. В Render нажмите **New → Blueprint**.
2. Подключите GitHub-репозиторий.
3. Render прочитает `render.yaml`.
4. Заполните переменные, где стоит `sync: false`.
5. Создайте сервис.

Вариант B, вручную:

```text
New → Web Service
Runtime: Python
Root Directory: пусто, если в репозитории только эта папка
Build Command: pip install -e .
Pre-Deploy Command: alembic upgrade head && python scripts/seed.py
Start Command: uvicorn app.main:app --host 0.0.0.0 --port $PORT
Plan: Free
Health Check Path: /health
```

## Настройка webhook для двух Telegram-ботов

После первого успешного деплоя нужно один раз выполнить локально:

```bash
cd vet-ai-manager-render
python -m venv .venv
source .venv/bin/activate
pip install -e .
export PUBLIC_BASE_URL=https://your-service-name.onrender.com
export TELEGRAM_CLIENT_BOT_TOKEN=...
export TELEGRAM_DOCTOR_BOT_TOKEN=...
python scripts/setup_webhooks.py
```

Будут настроены:

```text
клиентский бот → /api/webhooks/telegram
бот врача      → /api/webhooks/doctor-telegram
```

## Проверка

Откройте:

```text
https://your-service-name.onrender.com/
https://your-service-name.onrender.com/health
https://your-service-name.onrender.com/ready
```

Если `/ready` пишет, что doctor user не найден, проверьте `DOCTOR_TELEGRAM_USER_ID` и заново запустите deploy, чтобы сработали миграции и seed.

## Важное про бесплатный Render

Free Web Service засыпает после простоя. Первый ответ после сна может идти около минуты. Для демо и MVP это нормально, для рабочей клиники лучше платный тариф или VPS.
