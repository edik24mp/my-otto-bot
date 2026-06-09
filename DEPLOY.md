# Деплой OTTO Sales Mini App

## Быстрый деплой на GitHub Pages

1. Соберите:
```
npm run build
```
2. Файл `dist/index.html` — это всё приложение (464 KB, 147 KB gzip)

3. Залейте в репозиторий:
```bash
git checkout --orphan gh-pages
rm -rf ./*
cp ../dist/index.html ./index.html
git add index.html
git commit -m "Mini App deploy"
git push origin gh-pages --force
```

4. Включите Pages: GitHub → Settings → Pages → Source: gh-pages / root

Готово: `https://<username>.github.io/my-otto-app/`

---

## Обновить URL в боте

`bot.py`:
```python
WEBAPP_URL = "https://<username>.github.io/my-otto-app/"
```
Перезапустите бота.

---

## Vercel

`vercel --prod`
Build: `npm run build`
Output: `dist`

---

## API URL

По умолчанию в App.tsx:
```ts
const API_URL = "https://sales-otto-bot.fly.dev/api/data";
```

Замените на ваш реальный сервер, где крутится бот с API на порту 8443.

Для CORS в боте уже стоит `Access-Control-Allow-Origin: *`
