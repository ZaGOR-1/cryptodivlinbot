"""Light structural tests for ``deploy/cryptodivlinbot.service``.

systemd's INI-ish format is forgiving but a misplaced key can still
silently break auto-restart (e.g. ``StartLimitIntervalSec`` belongs in
``[Unit]``, not ``[Service]``, on modern systemd). Catch those here so
they trip CI rather than only being noticed when a deploy ends up in
crash-loop forever.
"""
from __future__ import annotations

import configparser
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
UNIT_PATH = REPO_ROOT / "deploy" / "cryptodivlinbot.service"


@pytest.fixture(scope="module")
def unit() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser(
        # systemd allows duplicate keys in a section (e.g. multiple
        # SystemCallFilter= lines); ConfigParser doesn't by default.
        strict=False,
        interpolation=None,
    )
    cfg.read(UNIT_PATH, encoding="utf-8")
    return cfg


def test_unit_file_exists() -> None:
    assert UNIT_PATH.is_file(), f"systemd unit not found at {UNIT_PATH}"


def test_unit_has_required_sections(unit: configparser.ConfigParser) -> None:
    for section in ("Unit", "Service", "Install"):
        assert unit.has_section(section), f"missing [{section}] section"


def test_auto_restart_is_wired(unit: configparser.ConfigParser) -> None:
    """Restart on every abnormal exit, with a back-off."""
    assert unit.get("Service", "Restart") == "on-failure"
    # RestartSec accepts ``10s``, ``10``, ``10sec`` etc. — just sanity
    # check it's a non-zero value.
    assert unit.get("Service", "RestartSec").rstrip("s") not in ("", "0")


def test_crash_loop_guard_lives_in_unit_section(
    unit: configparser.ConfigParser,
) -> None:
    """``StartLimit*`` keys belong in [Unit] on modern systemd.

    If they migrate back into [Service], systemd silently ignores them
    and the crash-loop guard is gone. Pin the location.
    """
    assert unit.has_option("Unit", "StartLimitIntervalSec")
    assert unit.has_option("Unit", "StartLimitBurst")
    assert not unit.has_option("Service", "StartLimitIntervalSec")
    assert not unit.has_option("Service", "StartLimitBurst")


def test_runs_as_dedicated_unprivileged_user(
    unit: configparser.ConfigParser,
) -> None:
    assert unit.get("Service", "User") == "cryptodivlinbot"
    assert unit.get("Service", "Group") == "cryptodivlinbot"


def test_graceful_shutdown_signal(unit: configparser.ConfigParser) -> None:
    """PTB's run_polling() expects SIGINT for a clean shutdown."""
    assert unit.get("Service", "KillSignal") == "SIGINT"


def test_sandbox_hardening_present(unit: configparser.ConfigParser) -> None:
    """Spot-check the security hardening so a future edit can't quietly drop it."""
    assert unit.getboolean("Service", "NoNewPrivileges") is True
    assert unit.get("Service", "ProtectSystem") == "strict"
    assert unit.getboolean("Service", "ProtectHome") is True
    assert unit.getboolean("Service", "PrivateTmp") is True


def test_wantedby_multi_user(unit: configparser.ConfigParser) -> None:
    assert unit.get("Install", "WantedBy") == "multi-user.target"
