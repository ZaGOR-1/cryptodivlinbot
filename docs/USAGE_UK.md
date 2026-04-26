# Cryptodivlinbot — інструкція користувача (🇺🇦 UA)

Цей документ описує як налаштувати, запустити та користуватися ботом `cryptodivlinbot`.

> 📑 Інші мови: [English (README)](../README.md) · [Русский](./USAGE_RU.md)

---

## 1. Що робить бот

`cryptodivlinbot` — це Telegram-бот, який:

1. **Відстежує топ-N криптовалют** (за замовчуванням топ-10) за ринковою
   капіталізацією через CoinGecko (з фолбеком на Binance).
2. **Надсилає миттєвий алерт**, коли ціна якоїсь монети змінюється більше ніж
   на `SPIKE_THRESHOLD_PCT` (за замовчуванням **5%**) у вікні
   `SPIKE_WINDOW_MIN` (за замовчуванням **5 хв**).
3. **Надсилає регулярний дайджест** кожні `DIGEST_INTERVAL_MIN`
   (за замовчуванням **5 хв**) з поточними цінами та змінами всіх монет.
4. **Підтримує 3 мови інтерфейсу**: Українська, Русский, English.
5. **Керується через інлайн-кнопки** та slash-команди.
6. **Зберігає налаштування кожного чату** в SQLite (мова, підписка,
   індивідуальний поріг, історія алертів) — після перезапуску нічого не
   губиться.

---

## 2. Встановлення

### 2.1. Передумови

- Python 3.11 або новіший
- `pip` (іде з Python)
- Доступ в інтернет (для CoinGecko / Binance API)
- Telegram-акаунт

### 2.2. Створення Telegram-бота

1. Відкрий у Telegram чат з [@BotFather](https://t.me/BotFather).
2. Надішли `/newbot`, вкажи назву й username (має закінчуватися на `bot`).
3. BotFather видасть **токен** виду `1234567890:ABCdefGh-IJKLmnOPQRstuVWXyz`.
   Збережи його — це `TELEGRAM_BOT_TOKEN`.

### 2.3. Клонування і встановлення залежностей

```bash
git clone https://github.com/ZaGOR-1/cryptodivlinbot.git
cd cryptodivlinbot

python -m venv .venv
source .venv/bin/activate          # на Windows: .venv\Scripts\activate

pip install -e '.[dev]'
```

### 2.4. Налаштування `.env`

```bash
cp .env.example .env
```

Відкрий `.env` будь-яким редактором і впиши свій токен:

```env
TELEGRAM_BOT_TOKEN=1234567890:ABCdefGh-IJKLmnOPQRstuVWXyz
```

Усі інші змінні мають розумні значення за замовчуванням — їх можна не чіпати.

---

## 3. Запуск

```bash
python -m cryptodivlinbot
```

У логах має з'явитися щось подібне:

```
2026-04-25 17:50:00 INFO cryptodivlinbot.bot: Started: top_n=10 threshold=5.00% window=5m digest=5m
```

Тепер відкрий у Telegram свого бота, надішли `/start` і натисни **🔔 Підписатися**.

Щоб зупинити бот — `Ctrl+C` у терміналі.

---

## 4. Параметри (`.env`)

| Змінна | За замовч. | Опис |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | _(обов'язково)_ | Токен від `@BotFather`. |
| `TOP_N_COINS` | `10` | Скільки топ-монет за капіталізацією відстежувати. |
| `SPIKE_THRESHOLD_PCT` | `5.0` | Поріг (у %) для миттєвого алерту. |
| `SPIKE_WINDOW_MIN` | `5` | Часове вікно (хв), на якому рахується % зміна. |
| `POLL_INTERVAL_SEC` | `60` | Як часто опитуються ціни. |
| `DIGEST_INTERVAL_MIN` | `5` | Як часто надсилається регулярний дайджест. |
| `ALERT_COOLDOWN_MIN` | `15` | Кулдаун на алерт по одній монеті в одному чаті. |
| `DEFAULT_LANGUAGE` | `uk` | Мова за замовчуванням (`en`, `uk`, `ru`). |
| `DB_PATH` | `cryptodivlinbot.sqlite` | Файл SQLite з усім станом. |
| `COINGECKO_API_KEY` | _(порожньо)_ | Опціональний ключ CoinGecko Pro (вищі ліміти). |
| `COINGECKO_BASE_URL` | `https://api.coingecko.com/api/v3` | Можна вказати свій проксі. |
| `BINANCE_BASE_URL` | `https://api.binance.com` | Базовий URL для фолбеку. |
| `HTTP_TIMEOUT_SEC` | `10` | Тайм-аут HTTP-запитів. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`. |
| `BACKUP_DIR` | `backups` | Каталог для ротованих копій SQLite (створюється автоматично). |
| `BACKUP_INTERVAL_MIN` | `60` | Як часто створюється копія БД (хв). |
| `BACKUP_RETENTION_COUNT` | `24` | Скільки копій тримати. Старіші — видаляються. |
| `ADMIN_CHAT_IDS` | _(порожньо)_ | Список chat id адмінів (через кому) для команди `/broadcast`. |
| `PRIVACY_POLICY_URL` | _GitHub `docs/PRIVACY_POLICY.md`_ | Посилання, яке віддає `/privacy`. |
| `TERMS_OF_SERVICE_URL` | _GitHub `docs/TERMS_OF_SERVICE.md`_ | Посилання, яке віддає `/terms`. |
| `SENTRY_DSN` | _(порожньо)_ | DSN Sentry / GlitchTip. Порожнє = моніторинг вимкнено. Потребує `pip install '.[monitoring]'`. |
| `SENTRY_ENVIRONMENT` | `production` | Тег середовища у Sentry. |
| `SENTRY_TRACES_SAMPLE_RATE` | `0.0` | Частка трасування продуктивності (0.0 – 1.0). |

> 💡 Якщо хочеш частіших алертів для тестів — постав `SPIKE_THRESHOLD_PCT=0.5`
> та `POLL_INTERVAL_SEC=30`. Просто не забудь повернути на робочі значення.

---

## 5. Команди

| Команда | Що робить |
| --- | --- |
| `/start` | Привітання + головне меню з кнопками. |
| `/menu` | Інлайн-кнопки швидких дій. |
| `/help` | Повний список команд. |
| `/status` | Стан підписки і поточні налаштування. |
| `/subscribe` | Почати отримувати алерти в цьому чаті. |
| `/unsubscribe` | Припинити отримувати алерти. |
| `/coins` | Список монет, що зараз відстежуються. |
| `/digest` | Надіслати дайджест прямо зараз. |
| `/language` | Інлайн-вибір мови. |
| `/setlang <en\|uk\|ru>` | Встановити мову напряму. |
| `/setthreshold <percent>` | Свій поріг сплеску для цього чату (`0.1` – `100`). |
| `/ping` | Перевірка стану — має відповісти `pong`. |
| `/broadcast <текст>` | **Лише для адмінів.** Розсилає `<текст>` (з HTML-розміткою) усім підписаним чатам. Доступна лише chat id, які вказано в `ADMIN_CHAT_IDS`. |
| `/privacy` | Коротко: які дані бот зберігає, плюс посилання на повну [Політику конфіденційності](./PRIVACY_POLICY_UK.md). |
| `/terms` | Коротко: умови користування, плюс посилання на повний [текст](./TERMS_OF_SERVICE_UK.md). |
| `/forgetme` | GDPR-видалення даних. Перший виклик — підтвердження; `/forgetme yes` остаточно стирає все, що бот зберігає про чат. |

---

## 6. Кнопки

Бот пропонує **два** варіанти кнопок одночасно — обирай те, що зручніше.

### 6.1. Закріплена клавіатура внизу чату (ReplyKeyboard)

Після `/start` під полем вводу зʼявляється постійна клавіатура з кнопками,
яка **залишається на місці між повідомленнями** (`is_persistent=True`,
`resize_keyboard=True`). Тапаєш на кнопку — бот виконує відповідну дію
так, ніби ти ввів команду:

- **🔔 Підписатися** — те саме, що `/subscribe`.
- **🔕 Відписатися** — те саме, що `/unsubscribe`.
- **📊 Статус** — `/status`.
- **📰 Дайджест зараз** — `/digest`.
- **🪙 Монети** — `/coins`.
- **🌐 Мова** — `/language` (відкриває inline-меню вибору мови).
- **❓ Довідка** — `/help`.

Підписи на кнопках автоматично перекладаються — після `/setlang ru` чи
вибору мови інлайн-кнопкою клавіатура внизу оновлюється з російськими
лейблами. Це закладено: `setlang` і callback `lang:<code>` повторно
надсилають клавіатуру з новим набором підписів.

### 6.2. Inline-меню в повідомленні

Команда `/menu` відкриває компактне inline-меню з тими самими діями
(і додатково кнопками **⬅️ Назад** і **✖️ Закрити**). Воно зручніше для
сценаріїв, у яких треба робити серію дій у межах одного повідомлення
(`Назад` повертає до головного меню без пересилання нового). Кнопка
**🌐 Мова** відкриває `language_menu` з прапорцями.

---

## 7. Як працюють алерти

### 7.1. Spike-алерт

Кожні `POLL_INTERVAL_SEC` секунд бот:
1. Отримує поточну ціну топ-N монет.
2. Записує її в історію (SQLite).
3. Для кожної монети порівнює найсвіжішу ціну з найстарішою в межах
   `SPIKE_WINDOW_MIN` хв.
4. Якщо абсолютна % зміна ≥ `SPIKE_THRESHOLD_PCT` (або індивідуального порога
   чату) — надсилає алерт.
5. Після успішно надісланого алерту запускається кулдаун
   `ALERT_COOLDOWN_MIN` для пари (чат, монета), щоб не спамити.

> ℹ️ Кулдаун запускається тільки якщо алерт реально дійшов. Якщо була
> мережева помилка — на наступному циклі бот спробує знову.

### 7.2. Дайджест

Кожні `DIGEST_INTERVAL_MIN` хв бот надсилає підписаним чатам список усіх
відстежуваних монет з:
- поточною ціною,
- зміною за останні `SPIKE_WINDOW_MIN` хв,
- зміною за 24 години.

---

## 8. Часті задачі

### 8.1. Тимчасово знизити поріг для конкретного чату

```
/setthreshold 1.5
```

Тепер цей чат буде отримувати алерти при русі ≥ 1.5 %, інші чати — за
глобальним налаштуванням.

### 8.2. Перемкнути мову

Натисни **🌐 Мова** і обери потрібну, або:

```
/setlang ru
```

### 8.3. Подивитися, що зараз у базі

`DB_PATH` — це звичайний SQLite-файл. Можна відкрити, наприклад,
`sqlite3 cryptodivlinbot.sqlite`:

```sql
SELECT * FROM chats;
SELECT coin_id, COUNT(*) FROM price_history GROUP BY coin_id;
```

---

## 9. Розробка та тестування

```bash
# Лінт
python -m ruff check .

# Перевірка типів (--strict)
python -m mypy src/cryptodivlinbot

# Тести
python -m pytest -q
```

Усі модулі покриті тестами: `alerts`, `i18n`, `state`, `market_data`,
`config`, `_safe_send`. Увесь пакет проходить `mypy --strict` —
конфігурація в `pyproject.toml`, секція `[tool.mypy]`. Якщо змінюєш
типізацію, варто запускати ті самі три команди локально перед пушем —
це рівно те, що CI робить на кожен PR.

---

## 10. Troubleshooting

| Проблема | Можлива причина / Як полагодити |
| --- | --- |
| `TELEGRAM_BOT_TOKEN is required` | Не вказаний токен у `.env` або змінній оточення. |
| `Unauthorized` від Telegram | Неправильний токен. Перевір копіпаст. |
| Бот не відповідає на повідомлення | Перевір, що процес запущений, і що ти спілкуєшся саме зі своїм ботом. |
| Алерти приходять занадто часто | Збільш `SPIKE_THRESHOLD_PCT` або `ALERT_COOLDOWN_MIN`. |
| Алерти не приходять зовсім | Постав `LOG_LEVEL=DEBUG`, поглянь у лог. Можливо, CoinGecko тимчасово недоступний — бот переключиться на Binance, але тільки для відомих монет. |
| `429 Too Many Requests` від CoinGecko | Збільш `POLL_INTERVAL_SEC` або додай `COINGECKO_API_KEY`. |

---

## 11. Запуск через Docker

У репо є multi-stage [`Dockerfile`](../Dockerfile) і
[`docker-compose.yml`](../docker-compose.yml) для продакшен-деплою.

### 11.1. Швидкий старт

```bash
cp .env.example .env             # відкрий .env і встав TELEGRAM_BOT_TOKEN
docker compose up -d --build     # збере образ і запустить у фоні
docker compose logs -f bot       # подивитись лог у реальному часі
```

Все. Бот вже працює.

### 11.2. Що всередині

- **Stage 1 (`builder`)**: `python:3.12-slim`, ставить `build-essential` і
  створює venv у `/opt/venv` з усіма runtime-залежностями (без `pytest`,
  `ruff` тощо — тільки те, що потрібно в проді).
- **Stage 2 (`runtime`)**: чистий `python:3.12-slim`, копіює venv з
  builder, створює непривілейованого користувача `app`, працює від нього.
  Це дрібний нюанс, але важливий для security: контейнер не зможе
  перезаписати `/etc` чи `/usr` навіть якщо в ньому щось зламають.
- **Розмір**: ~134 МБ (більшість — це сам Python).
- **HEALTHCHECK**: запускає `python -c "import cryptodivlinbot, cryptodivlinbot.config"`
  кожні 30 с. Якщо процес жорстко зависне, оркестратор (Docker /
  Kubernetes) побачить `unhealthy` і перезапустить.

### 11.3. Що задано в `docker-compose.yml`

- `restart: unless-stopped` — автоматичний рестарт при падінні / ребуті
  хоста.
- `env_file: .env` — токен і всі параметри підвантажуються з `.env`
  поряд з `docker-compose.yml`.
- `volumes: cryptodivlinbot_data:/data` — SQLite живе у named volume,
  тож `docker compose down && docker compose up` не губить підписки.
- `deploy.resources.limits.memory: 256M` — обмеження пам'яті. Бот легко
  вкладається в 50 МБ; ліміт є на випадок витоку.
- `logging: json-file` з ротацією 10 МБ × 5 файлів — диск не
  заллється навіть якщо бот лежить тижнями.

### 11.4. Корисні команди

```bash
docker compose ps                # статус контейнера + healthcheck
docker compose logs -f --tail 100 bot
docker compose restart bot       # рестарт без перезбору образу
docker compose pull && docker compose up -d --build   # оновлення
docker compose down              # зупинити (volume залишається)
docker compose down -v           # зупинити + видалити volume (зітре БД!)

# Зайти в контейнер для дебагу:
docker compose exec bot bash     # ні, у slim немає bash, ось правильний варіант:
docker compose exec bot python -c "import cryptodivlinbot.config as c; print(c.Settings.from_env())"

# Подивитись що в БД:
docker run --rm -v cryptodivlinbot_data:/data alpine sh -c "ls -la /data && wc -c /data/*.sqlite"
```

### 11.5. Тестування образу без compose

```bash
docker build -t cryptodivlinbot:test .
docker run --rm -e TELEGRAM_BOT_TOKEN=fake cryptodivlinbot:test \
  python -c "from cryptodivlinbot.bot import build_application; \
             app = build_application(); print('handlers:', sum(len(h) for h in app.handlers.values()))"
```

Якщо вивело `handlers: 13` — образ робочий.

### 11.6. Troubleshooting

| Проблема | Що робити |
| --- | --- |
| `TELEGRAM_BOT_TOKEN is required` | Не створив `.env` поряд з `docker-compose.yml` або не вписав туди токен. |
| Контейнер у статусі `unhealthy` | `docker compose logs bot` — швидше за все `Unauthorized` (поганий токен) або немає інтернету. |
| `permission denied` на volume | На SELinux-системах: `chcon -Rt svirt_sandbox_file_t ./data` або додай `:Z` у volume mount. |
| Хочу побачити, що збилось | `docker compose build --progress=plain --no-cache .` для повного логу. |

---

## 12. Безперервна інтеграція (GitHub Actions CI)

Файл [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) автоматично
запускається на:

- кожен `pull_request` (будь-яка гілка → `main`);
- кожен `push` у `main`.

### 12.1. Що робить пайплайн

Job `lint-and-test` виконує по черзі:

1. `actions/checkout@v4` — клонує репо.
2. `actions/setup-python@v5` — ставить Python з кешем `pip`
   (ключ — хеш `pyproject.toml`, тож встановлення залежностей наступних
   ранів зазвичай займає секунди).
3. `pip install -e '.[dev]'` — пакет у editable-режимі + dev-екстра
   (`pytest`, `pytest-asyncio`, `ruff`, `mypy`).
4. `python -m ruff check .` — лінтер.
5. `python -m mypy src/cryptodivlinbot` — типи у режимі `--strict`
   (конфіг у `pyproject.toml`, секція `[tool.mypy]`). Якщо в коді
   з'являється `Any`, відсутня анотація чи невикористаний `# type:
   ignore` — пайплайн впаде.
6. `python -m pytest -q` — увесь тестовий пакет (56 тестів).

Job запускається на матриці **Python 3.11** і **Python 3.12** з
`fail-fast: false` — якщо одна версія падає, друга все одно дороблюється,
щоб одразу видно було, чи це версійно-специфічна помилка.

### 12.2. Concurrency

`concurrency.group: ci-${{ github.workflow }}-${{ github.ref }}` з
`cancel-in-progress: true` — якщо ти пушиш у PR кілька комітів підряд,
старі рани автоматично скасовуються, GitHub-хвилини не палять зайвого.

### 12.3. Як читати результат

- **Статус-бейдж** у `README.md` (`![CI]…`) — клік веде у вкладку
  Actions, останній ран на `main`.
- На сторінці PR унизу видно ✅/❌ напроти `lint + tests (py 3.11)` та
  `lint + tests (py 3.12)`. Клік по назві → повний лог.
- Якщо ruff/pytest падає, у логах буде така ж помилка, як і локально —
  виправляй і пуш у ту ж гілку, рани перезапустяться автоматично.

### 12.4. Запустити те саме локально

```bash
pip install -e '.[dev]'
python -m ruff check .
python -m mypy src/cryptodivlinbot
python -m pytest -q
```

Якщо всі чотири команди зелені локально, CI буде зелений.

### 12.5. Permissions

В пайплайні явно вказано `permissions: contents: read` — він не може
писати в репо, не має доступу до секретів, не публікує артефакти. Це
відповідає принципу мінімальних привілеїв і безпечно для PR-ів від
сторонніх форків.

---

## 13. Що далі (плани розвитку)

Цей бот — повноцінний MVP. Природні наступні кроки:

- ✅ ~~CI на GitHub Actions (ruff + pytest на кожен PR)~~ — реалізовано в
  розділі 12.
- ✅ ~~Dockerfile / `docker-compose.yml` для деплою~~ — реалізовано в
  розділі 11.
- Команди `/mute <coin>` і `/topmovers`.
- Налаштовуваний список монет (не тільки топ-N).
- Налаштовуваний формат сповіщень (HTML, MarkdownV2).
- Алерти за технічними рівнями (горизонтальні рівні підтримки/опору).

Усі зміни Devin записує в [`CHANGELOG.md`](../CHANGELOG.md).
