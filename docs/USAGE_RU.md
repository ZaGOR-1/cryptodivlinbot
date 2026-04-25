# Cryptodivlinbot — инструкция пользователя (🇷🇺 RU)

Этот документ описывает, как настроить, запустить и пользоваться ботом
`cryptodivlinbot`.

> 📑 Другие языки: [English (README)](../README.md) · [Українська](./USAGE_UK.md)

---

## 1. Что делает бот

`cryptodivlinbot` — это Telegram-бот, который:

1. **Отслеживает топ-N криптовалют** (по умолчанию топ-10) по рыночной
   капитализации через CoinGecko (с фолбеком на Binance).
2. **Шлёт мгновенный алерт**, когда цена монеты меняется более чем на
   `SPIKE_THRESHOLD_PCT` (по умолчанию **5%**) в окне `SPIKE_WINDOW_MIN`
   (по умолчанию **5 мин**).
3. **Шлёт регулярный дайджест** каждые `DIGEST_INTERVAL_MIN`
   (по умолчанию **5 мин**) с текущими ценами и изменениями всех монет.
4. **Поддерживает 3 языка интерфейса**: Українська, Русский, English.
5. **Управляется инлайн-кнопками** и slash-командами.
6. **Сохраняет настройки каждого чата** в SQLite (язык, подписка,
   индивидуальный порог, история алертов) — после рестарта ничего не
   теряется.

---

## 2. Установка

### 2.1. Требования

- Python 3.11 или новее
- `pip` (идёт с Python)
- Доступ в интернет (для CoinGecko / Binance API)
- Telegram-аккаунт

### 2.2. Создание Telegram-бота

1. Откройте в Telegram чат с [@BotFather](https://t.me/BotFather).
2. Отправьте `/newbot`, укажите имя и username (должен оканчиваться на `bot`).
3. BotFather выдаст **токен** вида `1234567890:ABCdefGh-IJKLmnOPQRstuVWXyz`.
   Сохраните его — это `TELEGRAM_BOT_TOKEN`.

### 2.3. Клонирование и установка зависимостей

```bash
git clone https://github.com/ZaGOR-1/cryptodivlinbot.git
cd cryptodivlinbot

python -m venv .venv
source .venv/bin/activate          # в Windows: .venv\Scripts\activate

pip install -e '.[dev]'
```

### 2.4. Настройка `.env`

```bash
cp .env.example .env
```

Откройте `.env` любым редактором и впишите свой токен:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGh-IJKLmnOPQRstuVWXyz
```

Все остальные переменные имеют разумные значения по умолчанию — их можно
не трогать.

---

## 3. Запуск

```bash
python -m cryptodivlinbot
```

В логах должно появиться что-то вроде:

```
2026-04-25 17:50:00 INFO cryptodivlinbot.bot: Started: top_n=10 threshold=5.00% window=5m digest=5m
```

Теперь откройте в Telegram своего бота, отправьте `/start` и нажмите
**🔔 Подписаться**.

Чтобы остановить бот — `Ctrl+C` в терминале.

---

## 4. Параметры (`.env`)

| Переменная | По умолч. | Описание |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | _(обязательно)_ | Токен от `@BotFather`. |
| `TOP_N_COINS` | `10` | Сколько топ-монет по капитализации отслеживать. |
| `SPIKE_THRESHOLD_PCT` | `5.0` | Порог (в %) для мгновенного алерта. |
| `SPIKE_WINDOW_MIN` | `5` | Окно (мин), на котором считается % изменение. |
| `POLL_INTERVAL_SEC` | `60` | Как часто опрашиваются цены. |
| `DIGEST_INTERVAL_MIN` | `5` | Как часто шлётся регулярный дайджест. |
| `ALERT_COOLDOWN_MIN` | `15` | Кулдаун на алерт по одной монете в одном чате. |
| `DEFAULT_LANGUAGE` | `uk` | Язык по умолчанию (`en`, `uk`, `ru`). |
| `DB_PATH` | `cryptodivlinbot.sqlite` | Файл SQLite со всем состоянием. |
| `COINGECKO_API_KEY` | _(пусто)_ | Опциональный ключ CoinGecko Pro (выше лимиты). |
| `COINGECKO_BASE_URL` | `https://api.coingecko.com/api/v3` | Можно указать свой прокси. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Базовый URL для фолбека. |
| `HTTP_TIMEOUT_SEC` | `10` | Таймаут HTTP-запросов. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |

> 💡 Если хотите более частые алерты для тестов — поставьте
> `SPIKE_THRESHOLD_PCT=0.5` и `POLL_INTERVAL_SEC=30`. Только не забудьте
> вернуть рабочие значения.

---

## 5. Команды

| Команда | Что делает |
| --- | --- |
| `/start` | Приветствие + главное меню с кнопками. |
| `/menu` | Инлайн-кнопки быстрых действий. |
| `/help` | Полный список команд. |
| `/status` | Состояние подписки и текущие настройки. |
| `/subscribe` | Начать получать алерты в этом чате. |
| `/unsubscribe` | Перестать получать алерты. |
| `/coins` | Список отслеживаемых монет. |
| `/digest` | Отправить дайджест прямо сейчас. |
| `/language` | Инлайн-выбор языка. |
| `/setlang <en\|uk\|ru>` | Установить язык напрямую. |
| `/setthreshold <percent>` | Свой порог скачка для этого чата (`0.1` – `100`). |
| `/ping` | Проверка состояния — должен ответить `pong`. |

---

## 6. Кнопки

Все команды дублируются инлайн-кнопками. Нажмите `/menu` или `/start`,
чтобы увидеть главное меню:

- **🔔 Подписаться / 🔕 Отписаться** — включить/выключить алерты в чате.
- **📊 Статус** — показать текущие настройки.
- **📰 Дайджест сейчас** — отправить дайджест без ожидания таймера.
- **🪙 Монеты** — список отслеживаемых монет.
- **🌐 Язык** — переключить язык интерфейса.
- **❓ Справка** — список команд.
- **✖️ Закрыть** — закрыть меню.

---

## 7. Как работают алерты

### 7.1. Spike-алерт

Каждые `POLL_INTERVAL_SEC` секунд бот:
1. Получает текущую цену топ-N монет.
2. Записывает её в историю (SQLite).
3. Для каждой монеты сравнивает самую свежую цену с самой старой в пределах
   `SPIKE_WINDOW_MIN` мин.
4. Если абсолютное % изменение ≥ `SPIKE_THRESHOLD_PCT` (или индивидуального
   порога чата) — шлёт алерт.
5. После успешно отправленного алерта запускается кулдаун
   `ALERT_COOLDOWN_MIN` для пары (чат, монета), чтобы не спамить.

> ℹ️ Кулдаун запускается только если алерт реально дошёл. Если была
> сетевая ошибка — на следующем цикле бот попробует снова.

### 7.2. Дайджест

Каждые `DIGEST_INTERVAL_MIN` мин бот шлёт подписанным чатам список всех
отслеживаемых монет с:
- текущей ценой,
- изменением за последние `SPIKE_WINDOW_MIN` мин,
- изменением за 24 часа.

---

## 8. Частые задачи

### 8.1. Временно понизить порог для конкретного чата

```
/setthreshold 1.5
```

Теперь этот чат будет получать алерты при движении ≥ 1.5 %, остальные чаты
останутся на глобальной настройке.

### 8.2. Переключить язык

Нажмите **🌐 Язык** и выберите нужный, или:

```
/setlang ru
```

### 8.3. Посмотреть, что сейчас в БД

`DB_PATH` — это обычный SQLite-файл. Можно открыть, например,
`sqlite3 cryptodivlinbot.sqlite`:

```sql
SELECT * FROM chats;
SELECT coin_id, COUNT(*) FROM price_history GROUP BY coin_id;
```

---

## 9. Разработка и тестирование

```bash
# Линт
python -m ruff check .

# Проверка типов (--strict)
python -m mypy src/cryptodivlinbot

# Тесты
python -m pytest -q
```

Все модули покрыты тестами: `alerts`, `i18n`, `state`, `market_data`,
`config`, `_safe_send`. Весь пакет проходит `mypy --strict` —
конфигурация в `pyproject.toml`, секция `[tool.mypy]`. Если меняешь
типизацию — запускай те же три команды локально перед пушем — это
ровно то, что CI делает на каждый PR.

---

## 10. Troubleshooting

| Проблема | Возможная причина / Как починить |
| --- | --- |
| `TELEGRAM_BOT_TOKEN is required` | Не указан токен в `.env` или переменной окружения. |
| `Unauthorized` от Telegram | Неправильный токен. Проверьте копипаст. |
| Бот не отвечает на сообщения | Убедитесь, что процесс запущен и вы пишете именно своему боту. |
| Алерты приходят слишком часто | Увеличьте `SPIKE_THRESHOLD_PCT` или `ALERT_COOLDOWN_MIN`. |
| Алерты не приходят вовсе | Поставьте `LOG_LEVEL=DEBUG`, посмотрите лог. Возможно, CoinGecko временно недоступен — бот переключится на Binance, но только для известных монет. |
| `429 Too Many Requests` от CoinGecko | Увеличьте `POLL_INTERVAL_SEC` или добавьте `COINGECKO_API_KEY`. |

---

## 11. Запуск через Docker

В репо есть multi-stage [`Dockerfile`](../Dockerfile) и
[`docker-compose.yml`](../docker-compose.yml) для продакшен-деплоя.

### 11.1. Быстрый старт

```bash
cp .env.example .env             # откройте .env и впишите TELEGRAM_BOT_TOKEN
docker compose up -d --build     # соберёт образ и запустит в фоне
docker compose logs -f bot       # лог в реальном времени
```

Всё. Бот уже работает.

### 11.2. Что внутри

- **Stage 1 (`builder`)**: `python:3.12-slim`, ставит `build-essential` и
  создаёт venv в `/opt/venv` со всеми runtime-зависимостями (без
  `pytest`, `ruff` и прочих dev-extras — только то, что нужно в проде).
- **Stage 2 (`runtime`)**: чистый `python:3.12-slim`, копирует venv из
  builder, создаёт непривилегированного пользователя `app`, работает от
  него. Это мелкий нюанс, но важный для security: контейнер не сможет
  переписать `/etc` или `/usr` даже если в нём что-то взломают.
- **Размер**: ~134 МБ (большая часть — сам Python).
- **HEALTHCHECK**: запускает `python -c "import cryptodivlinbot, cryptodivlinbot.config"`
  каждые 30 с. Если процесс жёстко зависнет, оркестратор (Docker /
  Kubernetes) увидит `unhealthy` и перезапустит.

### 11.3. Что задано в `docker-compose.yml`

- `restart: unless-stopped` — автоматический рестарт при падении / ребуте
  хоста.
- `env_file: .env` — токен и все параметры подгружаются из `.env`
  рядом с `docker-compose.yml`.
- `volumes: cryptodivlinbot_data:/data` — SQLite живёт в named volume,
  поэтому `docker compose down && docker compose up` не теряет подписки.
- `deploy.resources.limits.memory: 256M` — лимит памяти. Бот легко
  укладывается в 50 МБ; лимит на случай утечки.
- `logging: json-file` с ротацией 10 МБ × 5 файлов — диск не зальётся
  даже если бот стоит неделями.

### 11.4. Полезные команды

```bash
docker compose ps                # статус контейнера + healthcheck
docker compose logs -f --tail 100 bot
docker compose restart bot       # рестарт без пересборки
docker compose pull && docker compose up -d --build   # обновление
docker compose down              # остановить (volume останется)
docker compose down -v           # остановить + удалить volume (сотрёт БД!)

# Зайти в контейнер для дебага (в slim нет bash, поэтому:):
docker compose exec bot python -c "import cryptodivlinbot.config as c; print(c.Settings.from_env())"

# Посмотреть, что в БД:
docker run --rm -v cryptodivlinbot_data:/data alpine sh -c "ls -la /data && wc -c /data/*.sqlite"
```

### 11.5. Тестирование образа без compose

```bash
docker build -t cryptodivlinbot:test .
docker run --rm -e TELEGRAM_BOT_TOKEN=fake cryptodivlinbot:test \
  python -c "from cryptodivlinbot.bot import build_application; \
             app = build_application(); print('handlers:', sum(len(h) for h in app.handlers.values()))"
```

Если выдало `handlers: 13` — образ рабочий.

### 11.6. Troubleshooting

| Проблема | Что делать |
| --- | --- |
| `TELEGRAM_BOT_TOKEN is required` | Не создан `.env` рядом с `docker-compose.yml` или не вписан токен. |
| Контейнер в статусе `unhealthy` | `docker compose logs bot` — скорее всего `Unauthorized` (плохой токен) или нет интернета. |
| `permission denied` на volume | На SELinux-системах: `chcon -Rt svirt_sandbox_file_t ./data` или добавь `:Z` к volume mount. |
| Хочу увидеть, что сломалось при сборке | `docker compose build --progress=plain --no-cache .`. |

---

## 12. Непрерывная интеграция (GitHub Actions CI)

Файл [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) автоматически
запускается на:

- каждый `pull_request` (любая ветка → `main`);
- каждый `push` в `main`.

### 12.1. Что делает пайплайн

Job `lint-and-test` выполняет по порядку:

1. `actions/checkout@v4` — клонирует репо.
2. `actions/setup-python@v5` — ставит Python с кэшем `pip`
   (ключ — хэш `pyproject.toml`, поэтому установка зависимостей в
   последующих ранах обычно занимает секунды).
3. `pip install -e '.[dev]'` — пакет в editable-режиме + dev-экстра
   (`pytest`, `pytest-asyncio`, `ruff`, `mypy`).
4. `python -m ruff check .` — линтер.
5. `python -m mypy src/cryptodivlinbot` — типы в режиме `--strict`
   (конфиг в `pyproject.toml`, секция `[tool.mypy]`). Если в коде
   появляется `Any`, пропадает аннотация или появляется
   неиспользуемый `# type: ignore` — пайплайн упадёт.
6. `python -m pytest -q` — весь тестовый пакет (56 тестов).

Job запускается на матрице **Python 3.11** и **Python 3.12** с
`fail-fast: false` — если одна версия падает, вторая всё равно
доделывается, чтобы сразу было видно, является ли ошибка версионно-
специфичной.

### 12.2. Concurrency

`concurrency.group: ci-${{ github.workflow }}-${{ github.ref }}` с
`cancel-in-progress: true` — если в PR подряд приходит несколько коммитов,
старые раны автоматически отменяются, GitHub-минуты не тратятся впустую.

### 12.3. Как читать результат

- **Статус-бейдж** в `README.md` (`![CI]…`) — клик ведёт во вкладку
  Actions, последний ран на `main`.
- На странице PR внизу видны ✅/❌ напротив `lint + tests (py 3.11)` и
  `lint + tests (py 3.12)`. Клик по названию → полный лог.
- Если ruff/pytest падает, в логах будет та же ошибка, что и локально —
  исправляй и пушь в ту же ветку, раны перезапустятся автоматически.

### 12.4. Запустить то же локально

```bash
pip install -e '.[dev]'
python -m ruff check .
python -m mypy src/cryptodivlinbot
python -m pytest -q
```

Если все четыре команды зелёные локально, CI будет зелёным.

### 12.5. Permissions

В пайплайне явно указано `permissions: contents: read` — он не может
писать в репо, не имеет доступа к секретам, не публикует артефакты. Это
соответствует принципу минимальных привилегий и безопасно для PR-ов от
сторонних форков.

---

## 13. Что дальше (планы развития)

Этот бот — полноценный MVP. Естественные следующие шаги:

- ✅ ~~CI на GitHub Actions (ruff + pytest на каждый PR)~~ — реализовано в
  разделе 12.
- ✅ ~~Dockerfile / `docker-compose.yml` для деплоя~~ — реализовано в
  разделе 11.
- Команды `/mute <coin>` и `/topmovers`.
- Настраиваемый список монет (не только топ-N).
- Настраиваемый формат уведомлений (HTML, MarkdownV2).
- Алерты по техническим уровням (горизонтальные уровни поддержки/сопротивления).

Все изменения Devin записывает в [`CHANGELOG.md`](../CHANGELOG.md).
