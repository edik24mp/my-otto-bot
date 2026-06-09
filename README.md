# OTTO Sales — Telegram Mini App

Telegram Mini App для контроля плана продаж. Фронтенд для вашего Python-бота.

Полностью готово к деплою на GitHub Pages / Vercel.

---

## 🎨 Дизайн

- Фон: `#0f172a`
- Карточки: `#1e293b`
- Акцент: оранжевый `#FFA500`
- Успех: `#22c55e`
- Ошибка: `#ef4444`
- Шрифт: Manrope / Inter

Стиль — чистый, современный, вдохновлён ottoplenie.com

---

## 📱 Экраны

1. **📊 Месяц** — дашборд текущего месяца
   - Прогресс-бары оплат / рентабельности
   - Метрики: отставание, нужно в день, день месяца
   - График: накопительная динамика план vs факт
   - Ежедневные оплаты столбцами

2. **📈 Год** — годовой дашборд
   - Столбцы план vs факт по месяцам
   - Рентабельность по месяцам
   - Таблица с детализацией

3. **📉 Динамика** — сравнение 2022-2026
   - Годовые столбцы
   - Рентабельность

4. **📋 Отчёт** — расширенный сводный отчёт
   - Новые / Постоянные клиенты
   - Средний чек
   - Динамика месяц к месяцу (зелёный / красный)

5. **💰 Премия** — только для `manager`
   - Выбор месяца (с сентября 2025)
   - Расчёт: факт × рент% × 1%

---

## 🔌 API

Бот уже реализован, трогать не нужно.

**Endpoint:** `POST /api/data`

Body:
```json
{ "initData": "<Telegram.WebApp.initData>" }
```

Где менять URL API в приложении:
`src/App.tsx`, строка ~118:
```ts
const API_URL = "https://sales-otto-bot.fly.dev/api/data";
```

Замените на свой: `http://your-server:8443/api/data` или `https://your-domain/api/data`

---

## 🚀 Локальный запуск

```bash
npm install
npm run dev
```

Откроется http://localhost:5173

**Вне Telegram:** приложение автоматически показывает MOCK-данные для разработки (июнь 2025, менеджер).
**Внутри Telegram:** автоматически берётся `Telegram.WebApp.initData` и делается реальный запрос к API.

---

## 📦 Сборка

```bash
npm run build
```

Получите `dist/index.html` — **один файл, ~462 KB**, всё заинлайнено (спасибо vite-plugin-singlefile).
Идеально для Telegram Mini App.

---

## 🌍 Деплой

### Вариант 1: GitHub Pages

1. В `vite.config.ts` уже стоит `base: './'` — ничего менять не нужно.
2. Соберите: `npm run build`
3. Залейте содержимое `dist/` в репозиторий `my-otto-app`, ветка `gh-pages`
   
   Быстрый способ:
   ```bash
   npm run build
   # скопируйте dist/index.html в корень gh-pages ветки
   git checkout --orphan gh-pages
   cp dist/index.html ./index.html
   git add index.html
   git commit -m "deploy"
   git push origin gh-pages --force
   ```
4. В настройках GitHub: Settings → Pages → Branch: gh-pages
5. Ваше приложение: `https://<username>.github.io/my-otto-app/`

**Не забудьте прописать URL в боте:**
`bot.py`, строка:
```python
WEBAPP_URL = "https://edik24mp.github.io/my-otto-app/"
```
Замените на свой.

### Вариант 2: Vercel (рекомендую)

1. Запушьте репозиторий на GitHub
2. Зайдите на vercel.com → New Project → Import repo
3. Build Command: `npm run build`
   Output Directory: `dist`
4. Deploy — готово.
5. URL вида `https://otto-sales.vercel.app`

Обновите `WEBAPP_URL` в боте.

### Вариант 3: Любой статический хостинг

Просто залейте `dist/index.html` — это единственный файл, который нужен.

---

## 🔐 Безопасность

- Бот верифицирует `initData` через HMAC-SHA256 (уже реализовано в `bot.py`)
- CORS: `Access-Control-Allow-Origin: *`
- Если пользователь не зарегистрирован в боте — API вернёт `{ "error": "not_registered" }`, приложение покажет "Сначала запусти бота"

---

## 🧩 Стек

- React 19
- Vite 7
- Tailwind CSS 4
- Chart.js 4 + react-chartjs-2
- @twa-dev/sdk (Telegram WebApp)
- vite-plugin-singlefile (всё в один HTML)

---

## 🔧 Настройки

| Что | Где |
|---|---|
| URL API | `src/App.tsx` → `API_URL` |
| Цвета темы | `src/App.tsx` → `COLORS` |
| Mock-данные | `src/App.tsx` → `MOCK_API` |
| URL WebApp в боте | `bot.py` → `WEBAPP_URL` |
| Порт API бота | `bot.py` → `API_PORT = 8443` |

---

## 📱 Telegram интеграция

- `WebApp.ready()` / `expand()`
- `BackButton` — показывает "Назад" при переходе с главного экрана
- `setHeaderColor('#0f172a')`
- Haptic feedback готов (можно добавить `WebApp.HapticFeedback`)

Кнопка в боте уже настроена:
```python
InlineKeyboardButton("📱 Открыть приложение", web_app=WebAppInfo(url=WEBAPP_URL))
```

---

## 🐛 Тестирование

Вне Telegram — mock-данные.
В Telegram — реальные.

Чтобы протестировать API локально:
```bash
# бот должен быть запущен
# API: http://localhost:8443/api/data
# поменяйте API_URL в App.tsx на http://localhost:8443/api/data
```

Telegram требует HTTPS для WebApp, для локального теста используйте ngrok / localtunnel.

---

MIT — свободно используйте.
