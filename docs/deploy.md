# Деплой

Для продакшен-окружения проекта **Reviews Analyzer** выбран [Render.com](https://render.com).

В облаке работает FastAPI и статический прототип лабы 2 по пути `/prototype/`. Прототип проверяет CSV в браузере и показывает демонстрационный отчёт. PostgreSQL и заглушки запускаются отдельно в локальном Compose.

## Хостинг: Render.com

Render выбран благодаря поддержке Docker, интеграции с GitHub, автоматическому развёртыванию и возможности получить публичный HTTPS-адрес.

## Как задеплоить

1. Авторизоваться на [render.com](https://render.com) через GitHub.
2. Выбрать **New → Web Service** → **Git Provider** и подключить репозиторий `vstu-sii/stream-6-smallindigroup`. Ветка должна быть опубликована на GitHub, а интеграции Render нужен доступ к репозиторию.
3. Для демонстрации лабы 2 выбрать ветку `lab2-delivery-design` и указать следующие параметры:
   - **Language:** Docker
   - **Root Directory:** оставить пустым
   - **Dockerfile Path:** `./Dockerfile`
   - **Docker Build Context Directory:** `.`
   - **Health Check Path:** `/health`
   - **Auto-Deploy:** On Commit

   Dockerfile в корне собирает API и файлы прототипа в один образ. Для Compose и проверок backend используется `backend/Dockerfile`.
4. Выбрать доступный тариф и нажать **Deploy Web Service**.
5. Дождаться успешной сборки и запуска контейнера.
6. Проверить `/`, `/health`, `/docs` и `/prototype/` по HTTPS. Все маршруты должны вернуть HTTP 200, а `/health` — `{"status":"ok"}`.
7. Записать проверенный HTTPS-адрес в этот документ и раздел Production в README.

**Прод-URL** — [Reviews Analyzer API](https://stream-6-smallindigroup.onrender.com/). [Прототип](https://stream-6-smallindigroup.onrender.com/prototype/).

После слияния Pull Request выбрать `main` в **Settings → Build & Deploy → Branch**. После развёртывания `main` повторить проверки по тому же HTTPS-адресу.

## Дальнейшие деплои

В режиме **On Commit** Render пересобирает и разворачивает приложение при изменениях в выбранной ветке GitHub. После переключения на `main` можно выбрать **After CI Checks Pass**, чтобы Render ждал результатов GitHub Actions.

GitHub Actions запускает lint, проверку форматирования, тесты и Docker build на Pull Request в `main` и при push в `main`.

## Известные ограничения

При использовании бесплатного тарифа Render сервис может переходить в спящий режим после простоя. Первый запрос после паузы может выполняться с задержкой.

Для демонстрационной версии лабораторной № 1 это допустимо.

## Переменные окружения

Для заглушки достаточно переменной `PORT`, которую задаёт Render. Uvicorn слушает `0.0.0.0` на порту `PORT` или `8000`, если переменная отсутствует. Дополнительные переменные при необходимости задаются в **Render Dashboard → Service → Environment**.

Секреты и пароли не должны храниться в репозитории. Файл `.env` используется только для локальной разработки, а `.env.example` содержит шаблон конфигурации.

## Откат

В **Render Dashboard → Service → Deploys** найдите предыдущий успешный деплой и выберите **Rollback → Rollback to this deploy**.

Проверьте `GET /health` после отката. Откат через Dashboard отключает Auto-Deploy. Включите его в **Settings** после исправления причины отката.
