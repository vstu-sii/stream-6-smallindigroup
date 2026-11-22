# Деплой

Для продакшен-окружения проекта **Reviews Analyzer** выбран [Render.com](https://render.com).

В облаке работает FastAPI и статический прототип лабы 2 по пути `/prototype/`. Прототип проверяет CSV в браузере и показывает демонстрационный отчёт. PostgreSQL и заглушки запускаются отдельно в локальном Compose.

## Текущая конфигурация Render

[Сервис stream-6-smallindigroup](https://dashboard.render.com/web/srv-dbuqub3rjlhs73b449j0/settings) собирается из репозитория `vstu-sii/stream-6-smallindigroup`.

| Параметр | Значение |
| --- | --- |
| Runtime | Docker |
| Branch | `lab2-delivery-design` |
| Root Directory | Пусто, используется корень репозитория |
| Dockerfile Path | `Dockerfile` |
| Docker Build Context Directory | `.` |

Корневой Dockerfile помещает API и файлы прототипа в один образ. Локальный Compose и проверки backend используют `backend/Dockerfile`.

## Дальнейшие деплои

Для ручного деплоя выберите **Deploys → Manual Deploy → Deploy latest commit**. После статуса **Live** проверьте, что [API](https://stream-6-smallindigroup.onrender.com/), [Swagger UI](https://stream-6-smallindigroup.onrender.com/docs), [прототип](https://stream-6-smallindigroup.onrender.com/prototype/) и [пример CSV](https://stream-6-smallindigroup.onrender.com/prototype/example.csv) отвечают HTTP 200, а [проверка состояния](https://stream-6-smallindigroup.onrender.com/health) возвращает `{"status":"ok"}`.

Когда корневой Dockerfile и прототип будут в `main`, можно переключить **Settings → Build → Branch** на `main` и повторить проверку. GitHub Actions проверяет pull request в `main` и пуши в `main`.

## Известные ограничения

При использовании бесплатного тарифа Render сервис может переходить в спящий режим после простоя. Первый запрос после паузы может выполняться с задержкой.

## Переменные окружения

Render задаёт `PORT`. Uvicorn слушает `0.0.0.0` на этом порту или на `8000`, если переменная отсутствует. Dockerfile задаёт `PROTOTYPE_DIR=/app/prototype`, из этой папки FastAPI отдаёт файлы по пути `/prototype/`.

Секреты и пароли не должны храниться в репозитории. Файл `.env` используется только для локальной разработки, а `.env.example` содержит шаблон конфигурации.

## Откат

В **Render Dashboard → Service → Deploys** найдите предыдущий успешный деплой и выберите **Rollback → Rollback to this deploy**.

Проверьте `GET /health` после отката. Откат через Dashboard отключает Auto-Deploy. Включите его в **Settings** после исправления причины отката.
