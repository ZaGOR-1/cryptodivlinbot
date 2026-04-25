"""Translations for the bot UI in English, Ukrainian, and Russian.

The :func:`t` helper is forgiving — if a key is missing in the requested locale it
falls back to ``en``, and if it's missing in ``en`` too it returns the key itself
(so a typo never blows up an entire handler with ``KeyError``).
"""
from __future__ import annotations

from typing import Any, Final

LANGUAGE_NAMES: Final[dict[str, str]] = {
    "en": "English",
    "uk": "Українська",
    "ru": "Русский",
}

LANGUAGE_FLAGS: Final[dict[str, str]] = {
    "en": "🇬🇧",
    "uk": "🇺🇦",
    "ru": "🇷🇺",
}

DEFAULT_LANGUAGE: Final[str] = "en"


TEXTS: Final[dict[str, dict[str, str]]] = {
    "en": {
        "start_greeting": (
            "Hi! I track the top-{top_n} cryptocurrencies and send you alerts when "
            "the price moves more than {threshold}% within {window} min, plus a "
            "regular digest every {digest} min.\n\n"
            "Use the buttons below or /help to see all commands."
        ),
        "help": (
            "Commands:\n"
            "/start — show greeting and main menu\n"
            "/menu — quick action buttons\n"
            "/help — this help\n"
            "/status — current settings and subscription\n"
            "/subscribe — start receiving alerts in this chat\n"
            "/unsubscribe — stop receiving alerts\n"
            "/coins — list tracked top coins\n"
            "/digest — send digest right now\n"
            "/language — choose interface language\n"
            "/setlang <en|uk|ru> — set language directly\n"
            "/setthreshold <percent> — change spike threshold for this chat\n"
            "/ping — health check"
        ),
        "menu_title": "Quick actions:",
        "btn_subscribe": "🔔 Subscribe",
        "btn_unsubscribe": "🔕 Unsubscribe",
        "btn_status": "📊 Status",
        "btn_digest": "📰 Digest now",
        "btn_coins": "🪙 Coins",
        "btn_language": "🌐 Language",
        "btn_help": "❓ Help",
        "btn_back": "⬅️ Back",
        "btn_close": "✖️ Close",
        "language_pick": "Choose interface language:",
        "language_set": "Language changed to {lang}.",
        "language_hint": "Use /language or /setlang <en|uk|ru>.",
        "bad_language": "Unknown language. Use: en, uk, ru.",
        "subscribed": "Subscribed. You'll receive alerts in this chat.",
        "unsubscribed": "Unsubscribed. No more alerts will be sent here.",
        "already_subscribed": "This chat is already subscribed.",
        "not_subscribed": "This chat is not subscribed.",
        "status_subscribed": "subscribed",
        "status_not_subscribed": "not subscribed",
        "status": (
            "Bot status\n"
            "  Subscription: {subscription}\n"
            "  Tracked coins: {top_n}\n"
            "  Spike threshold: {threshold}%\n"
            "  Spike window: {window} min\n"
            "  Digest interval: {digest} min\n"
            "  Cooldown: {cooldown} min\n"
            "  Language: {language}"
        ),
        "coins_header": "Tracked coins (top {top_n} by market cap):",
        "coins_empty": "No coin data yet — please try again in a minute.",
        "digest_empty": "No coin data yet — please try again in a minute.",
        "digest_header": "📰 Crypto digest (last {window} min):",
        "spike_alert_up": (
            "🚀 *{symbol}* ({name}) jumped *+{pct:.2f}%* in {window} min\n"
            "Price: ${price}"
        ),
        "spike_alert_down": (
            "📉 *{symbol}* ({name}) dropped *{pct:.2f}%* in {window} min\n"
            "Price: ${price}"
        ),
        "digest_line": "{symbol}: ${price} ({pct_str} {window}m, {pct_24h_str} 24h)",
        "threshold_set": "Spike threshold for this chat set to {value}%.",
        "threshold_usage": "Usage: /setthreshold <percent>. Allowed range: 0.1 – 100.",
        "bad_number": "Please enter a number.",
        "bad_threshold_range": "Threshold must be between 0.1 and 100%.",
        "pong": "pong",
        "permission_denied": "Permission denied.",
        "private_only": "This command works only in a private chat with the bot.",
        "n_a": "n/a",
    },
    "uk": {
        "start_greeting": (
            "Привіт! Я відстежую топ-{top_n} криптовалют і надсилаю алерти, коли "
            "ціна змінюється більше ніж на {threshold}% за {window} хв, а також "
            "регулярний дайджест кожні {digest} хв.\n\n"
            "Користуйся кнопками нижче або /help, щоб побачити всі команди."
        ),
        "help": (
            "Команди:\n"
            "/start — вітання та головне меню\n"
            "/menu — швидкі кнопки дій\n"
            "/help — ця довідка\n"
            "/status — поточні налаштування та підписка\n"
            "/subscribe — почати отримувати алерти в цьому чаті\n"
            "/unsubscribe — припинити отримувати алерти\n"
            "/coins — список відстежуваних монет\n"
            "/digest — надіслати дайджест зараз\n"
            "/language — вибрати мову інтерфейсу\n"
            "/setlang <en|uk|ru> — встановити мову напряму\n"
            "/setthreshold <percent> — змінити поріг сплеску для цього чату\n"
            "/ping — перевірка стану"
        ),
        "menu_title": "Швидкі дії:",
        "btn_subscribe": "🔔 Підписатися",
        "btn_unsubscribe": "🔕 Відписатися",
        "btn_status": "📊 Статус",
        "btn_digest": "📰 Дайджест зараз",
        "btn_coins": "🪙 Монети",
        "btn_language": "🌐 Мова",
        "btn_help": "❓ Довідка",
        "btn_back": "⬅️ Назад",
        "btn_close": "✖️ Закрити",
        "language_pick": "Оберіть мову інтерфейсу:",
        "language_set": "Мову змінено на {lang}.",
        "language_hint": "Використовуйте /language або /setlang <en|uk|ru>.",
        "bad_language": "Невідома мова. Доступні: en, uk, ru.",
        "subscribed": "Підписано. Алерти надходитимуть у цей чат.",
        "unsubscribed": "Відписано. Алерти більше не надходитимуть сюди.",
        "already_subscribed": "Цей чат уже підписаний.",
        "not_subscribed": "Цей чат не підписаний.",
        "status_subscribed": "підписаний",
        "status_not_subscribed": "не підписаний",
        "status": (
            "Стан бота\n"
            "  Підписка: {subscription}\n"
            "  Монет: {top_n}\n"
            "  Поріг сплеску: {threshold}%\n"
            "  Вікно сплеску: {window} хв\n"
            "  Інтервал дайджесту: {digest} хв\n"
            "  Кулдаун: {cooldown} хв\n"
            "  Мова: {language}"
        ),
        "coins_header": "Відстежувані монети (топ {top_n} за капіталізацією):",
        "coins_empty": "Даних ще немає — спробуйте за хвилину.",
        "digest_empty": "Даних ще немає — спробуйте за хвилину.",
        "digest_header": "📰 Крипто-дайджест (за останні {window} хв):",
        "spike_alert_up": (
            "🚀 *{symbol}* ({name}) зросла на *+{pct:.2f}%* за {window} хв\n"
            "Ціна: ${price}"
        ),
        "spike_alert_down": (
            "📉 *{symbol}* ({name}) впала на *{pct:.2f}%* за {window} хв\n"
            "Ціна: ${price}"
        ),
        "digest_line": "{symbol}: ${price} ({pct_str} {window}хв, {pct_24h_str} 24г)",
        "threshold_set": "Поріг сплеску для цього чату встановлено на {value}%.",
        "threshold_usage": "Використання: /setthreshold <percent>. Діапазон: 0.1 – 100.",
        "bad_number": "Введіть число.",
        "bad_threshold_range": "Поріг має бути в межах 0.1 – 100%.",
        "pong": "pong",
        "permission_denied": "Немає дозволу.",
        "private_only": "Ця команда працює лише в приватному чаті з ботом.",
        "n_a": "немає",
    },
    "ru": {
        "start_greeting": (
            "Привет! Я отслеживаю топ-{top_n} криптовалют и присылаю алерты, когда "
            "цена меняется более чем на {threshold}% за {window} мин, а также "
            "регулярный дайджест каждые {digest} мин.\n\n"
            "Используй кнопки ниже или /help, чтобы увидеть все команды."
        ),
        "help": (
            "Команды:\n"
            "/start — приветствие и главное меню\n"
            "/menu — быстрые кнопки действий\n"
            "/help — эта справка\n"
            "/status — текущие настройки и подписка\n"
            "/subscribe — начать получать алерты в этом чате\n"
            "/unsubscribe — перестать получать алерты\n"
            "/coins — список отслеживаемых монет\n"
            "/digest — отправить дайджест сейчас\n"
            "/language — выбрать язык интерфейса\n"
            "/setlang <en|uk|ru> — установить язык напрямую\n"
            "/setthreshold <percent> — изменить порог скачка для этого чата\n"
            "/ping — проверка состояния"
        ),
        "menu_title": "Быстрые действия:",
        "btn_subscribe": "🔔 Подписаться",
        "btn_unsubscribe": "🔕 Отписаться",
        "btn_status": "📊 Статус",
        "btn_digest": "📰 Дайджест сейчас",
        "btn_coins": "🪙 Монеты",
        "btn_language": "🌐 Язык",
        "btn_help": "❓ Справка",
        "btn_back": "⬅️ Назад",
        "btn_close": "✖️ Закрыть",
        "language_pick": "Выберите язык интерфейса:",
        "language_set": "Язык изменён на {lang}.",
        "language_hint": "Используйте /language или /setlang <en|uk|ru>.",
        "bad_language": "Неизвестный язык. Доступны: en, uk, ru.",
        "subscribed": "Подписано. Алерты будут приходить в этот чат.",
        "unsubscribed": "Отписано. Алерты больше не будут приходить сюда.",
        "already_subscribed": "Этот чат уже подписан.",
        "not_subscribed": "Этот чат не подписан.",
        "status_subscribed": "подписан",
        "status_not_subscribed": "не подписан",
        "status": (
            "Состояние бота\n"
            "  Подписка: {subscription}\n"
            "  Монет: {top_n}\n"
            "  Порог скачка: {threshold}%\n"
            "  Окно скачка: {window} мин\n"
            "  Интервал дайджеста: {digest} мин\n"
            "  Кулдаун: {cooldown} мин\n"
            "  Язык: {language}"
        ),
        "coins_header": "Отслеживаемые монеты (топ {top_n} по капитализации):",
        "coins_empty": "Данных ещё нет — попробуйте через минуту.",
        "digest_empty": "Данных ещё нет — попробуйте через минуту.",
        "digest_header": "📰 Крипто-дайджест (за последние {window} мин):",
        "spike_alert_up": (
            "🚀 *{symbol}* ({name}) выросла на *+{pct:.2f}%* за {window} мин\n"
            "Цена: ${price}"
        ),
        "spike_alert_down": (
            "📉 *{symbol}* ({name}) упала на *{pct:.2f}%* за {window} мин\n"
            "Цена: ${price}"
        ),
        "digest_line": "{symbol}: ${price} ({pct_str} {window}мин, {pct_24h_str} 24ч)",
        "threshold_set": "Порог скачка для этого чата установлен на {value}%.",
        "threshold_usage": "Использование: /setthreshold <percent>. Диапазон: 0.1 – 100.",
        "bad_number": "Введите число.",
        "bad_threshold_range": "Порог должен быть в диапазоне 0.1 – 100%.",
        "pong": "pong",
        "permission_denied": "Нет доступа.",
        "private_only": "Эта команда работает только в приватном чате с ботом.",
        "n_a": "нет",
    },
}


def normalize_language(language: str | None) -> str:
    """Return a supported locale, falling back to :data:`DEFAULT_LANGUAGE`.

    Telegram exposes language codes like ``"en-US"`` — only the leading subtag is used.
    """
    if not language:
        return DEFAULT_LANGUAGE
    primary = language.lower().split("-", 1)[0]
    if primary in TEXTS:
        return primary
    return DEFAULT_LANGUAGE


def t(key: str, language: str | None = None, /, **kwargs: Any) -> str:
    """Translate ``key`` into ``language``, formatting with ``kwargs``.

    Falls back to English, then to the key itself if the key is missing everywhere.
    """
    lang = normalize_language(language)
    template = TEXTS.get(lang, {}).get(key)
    if template is None:
        template = TEXTS[DEFAULT_LANGUAGE].get(key, key)
    if not kwargs:
        return template
    try:
        return template.format(**kwargs)
    except (KeyError, IndexError):
        # Better to surface the raw template than crash the handler.
        return template
