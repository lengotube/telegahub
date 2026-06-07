# Telega HUB

Telega HUB - Telegram bot + WebApp для каталога моделей, платных подписок, платных постов, кастомных заказов, кабинета автора и админки.

Структура сделана по мотивам твоих проектов `crushok_robot` и `@Anonimchatik_robot`: Python, `src/`, `config.yaml`, FastAPI рядом с aiogram, Postgres через Docker Compose. WebApp вынесен в отдельную папку `webapp`, чтобы его удобно заливать на Vercel.

## Что уже есть

- Telegram bot: `/start`, кнопка открытия WebApp, `/admin`, обработка Telegram Stars.
- WebApp: лента, профиль модели, баланс, заявка автора, создание постов, заказы, вывод, админка.
- Backend API: Telegram `initData` auth, роли user/creator/admin, приватная выдача медиа, модерация анкет.
- Контент: фото/видео, аватар без лица, пробное видео, подписочные и платные посты.
- Деньги: внутренний баланс в Stars, пополнение через Stars invoice, комиссия автора 15%.
- Заказы: пользователь замораживает сумму, модель принимает/отклоняет, после загрузки видео сумма идет модели.

## Важное перед запуском

Для такого продукта обязательно держать 18+, модерацию, жалобы, запрет несовершеннолетних, запрет чужого/слитого контента и ручную проверку авторов. В каркасе уже есть подтверждение 18+, pending/approved для моделей и reports, но перед продом это надо усилить правилами, KYC/age-check и логами модерации.

## Локальный запуск backend

1. Создай `.env` из примера:

```bash
cp .env.example .env
```

2. Заполни:

```text
BOT_TOKEN=токен от BotFather
DATABASE_URL=postgres://postgres:root@postgres/telega_hub
PUBLIC_URL=https://api.example.com
WEBAPP_URL=https://your-webapp.vercel.app
BOT_ADMINS=твой_telegram_id
```

3. В `config.yaml` проверь:

```yaml
server:
  public_url: "https://api.example.com"
  webapp_url: "https://your-webapp.vercel.app"
```

4. Запусти:

```bash
docker compose up -d --build
```

5. Проверка:

```bash
curl http://localhost:5080/ping
curl http://localhost:5080/api/health
```

## Деплой backend на VPS

На сервер загружаешь корень проекта, кроме `.env` с локальными секретами. На сервере создаешь свой `.env`, потом:

```bash
docker compose up -d --build
docker compose logs -f bot
```

Backend должен быть доступен по HTTPS. Обычно ставишь nginx/Caddy перед портом `5080` и проксируешь на контейнер.

## Деплой WebApp на Vercel

В Vercel грузишь папку:

```text
webapp
```

Настройки Vercel:

```text
Root Directory: webapp
Framework Preset: Other
Build Command: пусто
Output Directory: пусто
```

В `webapp/config.js` ставишь публичный API:

```js
window.TELEGA_HUB_API_BASE = "https://api.example.com";
```

После деплоя получишь URL вида:

```text
https://telega-hub.vercel.app
```

Его указываешь в `.env` backend как `WEBAPP_URL`.

## BotFather

1. `/newbot` или существующий бот.
2. `/setmenubutton` -> выбрать бота -> `Web App` -> вставить URL Vercel.
3. `/setdomain` -> домен Vercel.
4. В `.env` backend поставить `BOT_TOKEN`.
5. Перезапустить Docker:

```bash
docker compose up -d --build
```

## Локальная проверка WebApp без Telegram

Открой `webapp/index.html` через любой статический сервер или Vercel preview. Если Telegram `initData` нет, включается dev auth через `X-Debug-User-Id`, потому что в `config.yaml` стоит:

```yaml
dev_auth_enabled: true
```

Для прода лучше поставить:

```yaml
dev_auth_enabled: false
```

## Что доделать перед продом

- Реальная модерация медиа: очередь, причины reject, авто-блокировка по жалобам.
- Проверка 5 секунд trial video через ffprobe.
- Отдельное object storage: S3/Selectel/Cloudflare R2 вместо локального `uploads`.
- Нормальный payout flow: ручное подтверждение вывода, история выплат, экспорт.
- Юридические документы: правила, согласие автора, DMCA/жалобы, privacy.
- Вебхуки вместо polling, если захочешь держать только HTTPS API без long-polling.
