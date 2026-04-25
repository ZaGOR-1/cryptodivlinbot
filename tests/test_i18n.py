"""i18n parity and fallback tests."""
from __future__ import annotations

import pytest

from cryptodivlinbot.i18n import LANGUAGE_NAMES, TEXTS, normalize_language, t


def test_all_languages_have_same_keys():
    en_keys = set(TEXTS["en"].keys())
    for lang, table in TEXTS.items():
        missing = en_keys - set(table.keys())
        extra = set(table.keys()) - en_keys
        assert not missing, f"{lang} is missing keys: {sorted(missing)}"
        assert not extra, f"{lang} has unexpected keys: {sorted(extra)}"


def test_language_names_cover_all_locales():
    assert set(LANGUAGE_NAMES.keys()) == set(TEXTS.keys())


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("en", "en"),
        ("uk", "uk"),
        ("ru", "ru"),
        ("en-US", "en"),
        ("uk-UA", "uk"),
        ("zz", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_normalize_language(raw, expected):
    assert normalize_language(raw) == expected


def test_t_basic_lookup():
    assert t("pong", "en") == "pong"
    assert t("pong", "uk") == "pong"


def test_t_falls_back_to_english_on_unknown_language():
    # Pretend French isn't registered: the lookup falls through to en.
    assert t("pong", "fr") == "pong"


def test_t_returns_key_when_missing_everywhere():
    assert t("__definitely_not_a_real_key__", "en") == "__definitely_not_a_real_key__"


def test_t_formats_kwargs():
    text = t("language_set", "en", lang="English")
    assert "English" in text


def test_t_swallows_missing_format_args():
    # If a template expects {x} and we pass nothing, we shouldn't crash —
    # we return the raw template instead.
    text = t("threshold_set", "en")  # template uses {value}
    assert "{value}" in text
