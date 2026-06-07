# Telega HUB WebApp

Статическая Telegram Mini App для Vercel.

## Деплой

1. Залей весь репозиторий на GitHub.
2. В Vercel создай проект из этого репозитория.
3. В `Root Directory` укажи `webapp`.
4. Framework Preset: `Other`.
5. Build Command оставь пустым.
6. Output Directory оставь пустым.
7. Перед деплоем в `webapp/config.js` замени `window.TELEGA_HUB_API_BASE` на публичный URL backend API.

Если не хочешь менять `config.js`, можно передать API в ссылке WebApp:

```text
https://your-webapp.vercel.app/?api=https%3A%2F%2Fapi.example.com
```
